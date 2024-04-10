# Bird-Watcher

A self-hosted web app to be placed on a micro computer (96boards or raspberry-pi). The app will use a connected camera to live-stream a video feed on demand and has the capability to auto-record and save small video snippets when motion (a bird for example) is detected in the designated camera area.

## Getting-Started

### Installing Requirements

On your device make sure to install `ffmpeg`  that should be on the PATH and some libraries: `libavformat-dev libavdevice-dev v4l-utils python3-dev`

#### For Debiam/Ubuntu

simply run `sudo apt-get install ffmpeg libavdevice-dev libavformat-dev v4l-utils python3-dev`

#### Installing pip requirements

Install the requirements in the requirements.txt file. (It is recommended to use a venv!)

Run `python3 -m pip install -r requirements.txt`

### Create a `.env` file

Before running the app you may have to edit some settings. All the settings can be found in the [Settings](#settings) section. You can leave most to the default, which should work fine. If your R-pi has performance issues try reducing the camera resolution.

**NB**: You must set at least the Django secret key.

### Running the WebApp

To run the app enter the `bird_watcher` directory and build the database (only needed once) then run the webapp with uvicorn:

```bash
cd bird_watcher
python3 manage.py makemigrations birdwatcher
python3 manage.py migrate
uvicorn bird_watcher_proj.asgi:app
```

The app is now accessible locally at [127.0.0.1:8000](http://127.0.0.1:8000)

You can add `--host 0.0.0.0` to accept connections on your LAN IP and on your public IP if your have your ports open.
You can also edit the listening port with `--port 12345` to open the app on port *12345* for example. **NB** To use ports  [1,1024] you may need to use sudo privileges.

### Running the motion detector

To run the motion detector part, ensure your settings are set and the camera is correctly oriented then in a new terminal run:

```bash
cd bird_watcher
python3 manage.py watch_motion
```

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
|VID_CAMERA_FORMAT|The camera feed decoder library. For linux `v4l2` works well and for OSX use `avfoundation` Other values can be found on [ffmpeg's documentation](https://trac.ffmpeg.org/wiki/Capture/Webcam)|`v4l2`|
|VID_INPUT_FORMAT|Different values are possible, usually `yuyv` and `mjpeg` are available for v4l2 webacams. `YUYV` has better image quality but a lower framerate at similar resolutions than `mjpeg` |`mjpeg`|
|VID_OUTPUT_PXL_FORMAT|The pixel format for the video output|`yuvj422p`|
|VID_RESOLUTION|The video resolution to be supplied by the camera. Depending on your choice of `VID_INPUT_FORMAT`, you can see available resolutions with the `ffmpeg -f v4l2 -list_formats all -i {VID_CAMERA_DEVICE}` command on linux.|`1280x720`|
|MOTION_CHECKS_PER_SECOND|The number of times per second to check for movement on a frame. Lower numbers have more change of missing an object that quickly enters and leaves the frame but is more sensitive because there is more variation between two check-frames|`2`|
|MOTION_DETECTION_THRESHOLD|The percentage of the screen that should change for it to be considered as a movement event. Should be between 0 and 1, lower values increase sensitivity. A value of 0 will always detect movement and a value of 1 will detect movement only if **ALL** pixels change between two check frames| `0.07`|
|RECORD_SECONDS_BEFORE_MOVEMENT|The number of seconds to save in the recording **before** movement was detected|`2`|
|RECORD_SECONDS_AFTER_MOVEMENT|The number of seconds to record in the same vide file after the last movement event was detected|`2`|
|VID_FORCED_FRAMERATE|Set this value to a non-negative integer of you want to force the camera framerate to a certain value. It may fix the video captured if it looks sped up. This setting is usually not used|`-1`|
