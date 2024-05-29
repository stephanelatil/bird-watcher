#!/bin/bash

echo '***********************\nInstalling libraries\n***********************'
sudo apt update
sudo apt-get install ffmpeg libavdevice-dev libavformat-dev v4l-utils python3-dev libsystemd-dev -y

echo '***********************\nSetting up venv\n***********************'
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt

echo '***********************\nRemoving unused packages\n***********************'
sudo apt autoremove

echo '***********************\nSetting Django Secrets\n***********************'
cp -u .env.dev .env
SECRET=`python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key().replace("&","-"))'`
sed "s/^DJANGO_SECRET_KEY=.*$/DJANGO_SECRET_KEY=$SECRET/g" .env -i
unset SECRET

echo '***********************\nSetting up Database\n***********************'
cd bird_watcher
python3 manage.py migrate
cd ..

echo '***********************\nAdding Unix Socket\n***********************'
read -n1 -p "Would you like to use a unix socket to distribute frames? (y/n): " answer
echo ''
if [[ "$answer" =~ ^[Yy]$ ]]; then
    sed "s/^DEVICE_DUPLICATION=.*$/DEVICE_DUPLICATION=socket/g" .env -i
    sed "s/^STREAM_VID_DEVICE=.*$/STREAM_VID_DEVICE=127.0.0.1/g" .env -i
    sed "s:^VID_CAMERA_DEVICE=.*$:VID_CAMERA_DEVICE=/dev/video0:g" .env -i
else
    read -n1 -p "Would you like to use v4l2loopback to duplicate camera device? If no a single frame will be available for streaming. Frame updated on first start and on motion detection restart. (y/n): " answer
    echo ''
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        # use v4l2loopback as device duplication
        echo '***********************\nAdding v4l2loopback\n***********************'
        sed "s/^DEVICE_DUPLICATION=.*$/DEVICE_DUPLICATION=v4l2loopback/g" .env -i
        sed "s:^STREAM_VID_DEVICE=.*$:STREAM_VID_DEVICE=/dev/video100:g" .env -i
        sed "s:^VID_CAMERA_DEVICE=.*$:VID_CAMERA_DEVICE=/dev/video100:g" .env -i
        sudo apt update && sudo apt install raspberrypi-kernel-headers -y
        sudo apt install v4l2loopback-dkms -y
        echo 'v4l2loopback' | sudo tee -a /etc/modules
        echo 'options v4l2loopback devices=1 video_nr=100 card_label="Birds"' | sudo tee '/etc/modprobe.d/v4l2loopback.conf'
    else
        #here no duplication and use static image generated on watch_motion start as live
        echo '***********************\Using no duplication\n***********************'
        sed "s/^DEVICE_DUPLICATION=.*$/DEVICE_DUPLICATION=none/g" .env -i
        sed "s:^VID_CAMERA_DEVICE=.*$:VID_CAMERA_DEVICE=/dev/video0:g" .env -i
        sed "s/^STREAM_VID_DEVICE=.*$/STREAM_VID_DEVICE=/g" .env -i
    fi
fi

echo '***********************\nAdding Services\n***********************'
sudo sh -c 'sed "s:^WorkingDirectory=.*:WorkingDirectory=`pwd`/bird_watcher/:g" services/birdwatcher-duplication.service > /etc/systemd/system/birdwatcher-duplication.service'
sudo sh -c 'sed -i "s:^ExecStart=.*:ExecStart=`pwd`/.venv/bin/python3 manage.py video_duplication:g" /etc/systemd/system/birdwatcher-duplication.service'
sudo sh -c 'sed "s:^WorkingDirectory=.*:WorkingDirectory=`pwd`/bird_watcher/:g" services/birdwatcher-webapp.service > /etc/systemd/system/birdwatcher-webapp.service'
sudo sh -c 'sed -i "s:^ExecStart=.*:ExecStart=`pwd`/.venv/bin/python3 manage.py run_webapp:g" /etc/systemd/system/birdwatcher-webapp.service'
sudo sh -c 'sed "s:^WorkingDirectory=.*:WorkingDirectory=`pwd`/bird_watcher/:g" services/birdwatcher-motion-detection.service > /etc/systemd/system/birdwatcher-motion-detection.service'
sudo sh -c 'sed -i "s:^ExecStart=.*:ExecStart=`pwd`/.venv/bin/python3 manage.py watch_motion:g" /etc/systemd/system/birdwatcher-motion-detection.service'
sudo systemctl daemon-reload

echo '***********************\nStarting And Enabling Services\n***********************'
# Prompt the user to enable services on reboot
read -n1 -p "Would you like to enable the services on reboot? (y/n): " answer
echo ''
if [[ "$answer" =~ ^[Yy]$ ]]; then
    sudo systemctl enable birdwatcher-duplication.service
    sudo systemctl enable birdwatcher-webapp.service
    echo "Services enabled on reboot."
fi
