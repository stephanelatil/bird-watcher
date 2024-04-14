#bin/bash

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root" 1>&2
   exit 1
fi

echo -e '***********************\nInstalling libraries\n***********************'
apt update
apt-get install ffmpeg libavdevice-dev libavformat-dev v4l-utils python3-dev libsystemd-dev -y

echo -e '***********************\nSetting up venv\n***********************'
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt

echo -e '***********************\nRemoving unused packages\n***********************'
apt autoremove

echo -e '***********************\nSetting Django Secrets\n***********************'
cp -u .env.dev .env
SECRET=`python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`
sed "s/^DJANGO_SECRET_KEY=.*/DJANGO_SECRET_KEY=$SECRET/g" .env -i
unset SECRET

echo -e '***********************\nSetting up Database\n***********************'
cd bird_watcher
python3 manage.py migrate
cd ..

echo -e '***********************\nAdding v4l2loopback\n***********************'
sudo apt update && sudo apt install raspberrypi-kernel-headers -y
sudo apt install v4l2loopback-dkms -y
echo 'v4l2loopback' | sudo tee -a /etc/modules
echo 'options v4l2loopback devices=1 video_nr=100 card_label="Birds"' | sudo tee '/etc/modprobe.d/v4l2loopback.conf'

echo -e '***********************\nAdding Services\n***********************'
cat services/birdwatcher-v4l2loopback.service > /etc/systemd/system/birdwatcher-v4l2loopback.service
sed "s:^WorkingDirectory=.*:WorkingDirectory=`pwd`/bird_watcher/:g" services/birdwatcher-webapp.service > /etc/systemd/system/birdwatcher-webapp.service
sed -i "s:^ExecStart=.*:ExecStart=`pwd`/.venv/bin/python3 manage.py run_webapp:g" /etc/systemd/system/birdwatcher-webapp.service
sed "s:^WorkingDirectory=.*:WorkingDirectory=`pwd`/bird_watcher/:g" services/birdwatcher-motion-detection.service > /etc/systemd/system/birdwatcher-motion-detection.service
sed -i "s:^ExecStart=.*:ExecStart=`pwd`/.venv/bin/python3 manage.py watch_motion:g" /etc/systemd/system/birdwatcher-motion-detection.service
systemctl daemon-reload

echo -e '***********************\nStarting And Enabling Services\n***********************'
# Prompt the user to enable services on reboot
read -n1 -p "Would you like to enable the services on reboot? (y/n): " answer
echo ''
if [[ "$answer" =~ ^[Yy]$ ]]; then
    systemctl enable birdwatcher-v4l2loopback.service
    systemctl enable birdwatcher-webapp.service
    echo "Services enabled on reboot."
fi
