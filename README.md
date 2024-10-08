# Bird-Watcher

A self-hosted web app to be placed on a micro computer (96boards or raspberry-pi). The app will use a connected camera to live-stream a video feed on demand and has the capability to auto-record and save small video snippets when motion (a bird for example) is detected in the designated camera area.

## Need an issue fixed faster?

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/stephanelatil)

## Quick-Start

To get up and running quickly simply clone this repo and run the setup.sh file. It will install all required libraries, python venv, setup the database and the services. It will also ask of you want to enable video device duplication with either a UNIX socket or v4l2loopback or none at all (answer no to the questions). The last questions asks if you want the webapp and motion detector to autostart on boot.

## Getting-Started

### Installing Requirements

On your device make sure to install `ffmpeg`  that should be on the PATH and some libraries: `libavformat-dev libavdevice-dev v4l-utils python3-dev libsystemd-dev`

#### For Debiam/Ubuntu

simply run `sudo apt-get install ffmpeg libavdevice-dev libavformat-dev v4l-utils python3-dev libsystemd-dev`

#### Installing pip requirements

Install the requirements in the requirements.txt file. (It is recommended to use a venv!)

To create the venv just run `python3 -m venv .venv` then run `. .venv/bin/activate`

Then install requirements by running `python3 -m pip install -r requirements.txt`

### Create a `.env` file

Before running the app you may have to edit some settings. All the settings can be found in the [Settings](#settings) section. You can leave most to the default, which should work fine. If your R-pi has performance issues try reducing the camera resolution.

**NB**: You must set at least the Django secret key.

### If Using Video Duplication

You may need to duplicate the video camera stream in some way if you want the live-stream tab to work. For that you need to enable `socket` duplication or `v4l2loopback` in the `.env` file.

**For additional info see:** [Enable live-streaming](#enable-live-streaming)

### Running the WebApp

#### Running it as a simple command

To run the app enter the `bird_watcher` directory and build the database (only needed once) then run the webapp with uvicorn:

```bash
cd bird_watcher
python3 manage.py migrate #only needed once to build the database, subsequent runs are not needed it but won't break anything if run multiple times
sudo python3 manage.py run_webapp
```

The app is now accessible by using the host and port set in the .env file.
**NB** *Superuser is necessary for starting and stopping the other microservices run as systemctl processes

#### Run it as a service

Using the service files in the `services` directory run it as a service so it auto-starts on boot! simply place the service files in `/etc/systemd/system/` and run them with `sudo systemctl start birdwatcher-webapp.service`

### Running the motion detector

To run the motion detector part, ensure your settings are set and the camera is correctly oriented then in a new terminal run:

```bash
cd bird_watcher
sudo python3 manage.py watch_motion
```

Or you can start it from the webapp directly. It will run until stopped (by the webapp), until the system reboots or until it crashes (may happen sorry).

## Application Parts

The app is based on the Django framework. Django will handle the backend and will also create the frontend with the help of bootstrap-v5. The motion detection will be done through a Django custom command on a second process.

### Motion detector

The motion detection that handles saving short videos where movement is detected.

This part of the project can be started by running `python3 bird_watcher/manage.py watch_motion` It will run until the enter key is pressed. If it hangs after the stop is requested you can force it by pressing `Ctrl-C` a few times.

The settings for the video encoding, and sensitivity of the movement detection can be set in the Django `.env` file or in environment variables. It will be automatically placed in the settings.py file on each run.

**NB:** If changing the `.env` file does not change the settings, try restarting your shell or clearing the environment variables.

### WebApp

*TODO* write paragraph

## Settings

### Required settings

These settings *must* be set as there is no default value for them. The value in the `Example Value` column may work but it is not guaranteed

|Key|Description|Example Value|
| --- | --- | --- |
|DJANGO_SECRET_KEY|The secret key used by Django to supply tokens and other hashes|To generate one use the `get_random_secret_key()` function from the `django.core.management.utils` package|

### Optional settings

|Key|Description|Default value|
| --- | --- | --- |
|VID_CAMERA_DEVICE|The device to read the camera input from. Usually in the `/dev` directory. It may not be video0 if it is a USB device with special drivers or if multiple cameras are connected|`/dev/video0`|
|VID_OUTPUT_PXL_FORMAT|The pixel format for the video output|`yuvj422p`|
|VID_RESOLUTION|The video resolution to be supplied by the camera. The input format is `yuyv422`, you can see available resolutions with the `ffmpeg -f v4l2 -list_formats all -i {VID_CAMERA_DEVICE}` command on linux.|`1280x720`|
|MOTION_CHECKS_PER_SECOND|The number of times per second to check for movement on a frame. Lower numbers have more change of missing an object that quickly enters and leaves the frame but is more sensitive because there is more variation between two check-frames|`2`|
|MOTION_DETECTION_THRESHOLD|The percentage of the screen that should change for it to be considered as a movement event. Should be between 0 and 1, lower values increase sensitivity. A value of 0 will always detect movement and a value of 1 will detect movement only if **ALL** pixels change between two check frames| `0.07`|
|RECORD_SECONDS_BEFORE_MOVEMENT|The number of seconds to save in the recording **before** movement was detected|`2`|
|RECORD_SECONDS_AFTER_MOVEMENT|The number of seconds to record in the same vide file after the last movement event was detected|`2`|
|VID_FORCED_FRAMERATE|Set this value to a non-negative integer of you want to force the camera framerate to a certain value. It may fix the video captured if it looks sped up. This setting is usually not used|`-1`|
|LOGGING_LEVEL| The logging level for the terminal. Logging is set to INFO for the log file. | WARNING |
|WEBAPP_HOST| | 127.0.0.1 |
|WEBAPP_PORT| | 8000 |

## Enable Live-streaming

To enable live-streaming you need to be able to have a loopback video device to be read by the service that handles live-streaming. To do that you need to install `v4l2loopback` on your device.

It will install v4l2loopback and set it up for autostart on reboot. It will add a loopback device /dev/video100
You can now set the /dev/video100 for the birdwatcher device and the livestream!

For Debian run

```bash
sudo apt update && sudo apt install raspberrypi-kernel-headers -y
sudo apt install v4l2loopback-dkms -y
echo 'v4l2loopback' | sudo tee -a /etc/modules
echo 'options v4l2loopback devices=1 video_nr=100 card_label="Birds"' | sudo tee '/etc/modprobe.d/v4l2loopback.conf'
```

Note that you will also have to send data to the loopback devices using the following command that will run in the background. Running it as a service using the `birdwatcher-duplication.service` file in the `services` folder or as a command.

### As a bash command

Note that this means the shell will be used and cannot be closed or the process will be killed! you can use nohup to send it to the background but it will not be run on reboot (if a crash or reboot happens)

```bash
sudo python3 manage.py video_duplication
```

### As a service

If running the webapp or motion-detector as a service this service will be run automatically. Or you can start it manually with:

```bash
sudo systemctl start birdwatcher-duplication.service
```
