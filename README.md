# Bird-Watcher

A self-hosted web app to be placed on a micro computer (96boards or raspberry-pi). The app will use a connected camera to live-stream a video feed on demand and has the capability to auto-record and save small video snippets when motion (a bird for example) is detected in the designated camera area.

## Getting-Started

### Installing Requirements

On your device make sure to install `ffmpeg` that should be on the PATH and some libraries: `libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev`

#### For Debiam/Ubuntu

simply run `sudo apt-get install ffmpeg libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev v4l-utils`

#### For Alpine Linux

Run `sudo apk install ffmpeg ffmpeg-libavformat ffmpeg-libavcodec ffmpeg-libavdevice ffmpeg-libavutil ffmpeg-libswscale ffmpeg-libswresample ffmpeg-libavfilter v4l-utils`

### Application Parts

The app is based on the Django framework. Django will handle the backend and will also create the frontend with the help of bootstrap-v5. The motion detection will be done through a Django custom command on a second process.

#### Motion detector

The motion detection that handles saving short videos where movement is detected.

This part of the project can be started by running `python3 bird_watcher/manage.py watch_motion` It will run until the enter key is pressed. If it hangs after the stop is requested you can force it by pressing `Ctrl-C` a few times.

The settings for the video encoding, and sensitivity of the movement detection can be set in the Django `.env` file or in environment variables. It will be automatically placed in the settings.py file on each run.

**NB:** If changing the `.env` file does not change the settings, try restarting your shell or clearing the environment variables.

##### Settings

###### Required settings

These settings *must* be set as there is no default value for them. The value in the `Example Value` column may work but it is not guaranteed

|Key|Description|Example Value|
| --- | --- | --- |
|VID_CAMERA_DEVICE|The device to read the camera input from. Usually in the `/dev` directory. It may not be video0 if it is a USB device with special drivers or if multiple cameras are connected|`/dev/video0`|
|DJANGO_SECRET_KEY|The secret key used by Django to supply tokens and other hashes|To generate one use the `get_random_secret_key()` function from the `django.core.management.utils` package|

###### Optional settings

|Key|Description|Default value|
| --- | --- | --- |
|VID_CAMERA_FORMAT|The camera feed decoder library. For linux `v4l2` works well and for OSX use `avfoundation` Other values can be found on [ffmpeg's documentation](https://trac.ffmpeg.org/wiki/Capture/Webcam)|`v4l2`|
|VID_INPUT_FORMAT||`mjpeg`|
|VID_OUTPUT_PXL_FORMAT|The pixel format **for** the video output|`yuvj444p`|
|VID_RESOLUTION|The video resolution to be supplied by the camera. Depending on your choice of `VID_INPUT_FORMAT`, you can see available resolutions with the `ffmpeg -f v4l2 -list_formats all -i {VID_CAMERA_DEVICE}` command on linux.||
|VID_FORCED_FRAMRATE||`-1` (Framerate auto-set by camera)|
|MOTION_CHECKS_PER_SECOND|||
|MOTION_DETECTION_THRESHOLD|||
|RECORD_SECONDS_BEFORE_MOVEMENT|||
|RECORD_SECONDS_AFTER_MOVEMENT|||
