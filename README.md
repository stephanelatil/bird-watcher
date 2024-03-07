# Bird-Watcher

A self-hosted web app to be placed on a micro computer (96boards or raspberry-pi). The app will use a connected camera to live-stream a video feed on demand and has the capability to auto-record and save small video snippets when motion (a bird for example) is detected in the designated camera area.

## Getting-Started

### Installing Requirements

On your device make sure to install `ffmpeg` that should be on the PATH and some libraries: `libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev`

#### For Debiam/Ubuntu

simply run `sudo apt-get install ffmpeg libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev`

#### For Alpine Linux

Run `sudo apk install ffmpeg ffmpeg-libavformat ffmpeg-libavcodec ffmpeg-libavdevice ffmpeg-libavutil ffmpeg-libswscale ffmpeg-libswresample ffmpeg-libavfilter`

### Application Parts

The app is based on the Django framework. Django will handle the backend and will also create the frontend with the help of bootstrap-v5. The motion detection will be done through a Django custom command on a second process.

#### Motion detector

The motion detection that handles saving short videos where movement is detected.

This part of the project can be started by running `python3 bird_watcher/manage.py watch_motion` It will run until the enter key is pressed. If it hangs after the stop is requested you can force it by pressing `Ctrl-C` a few times.

The settings for the video encoding, and sensitivity of the movement detection can be set in the Django `.env` file or in environment variables. It will be automatically placed in the settings.py file on each run.

**NB:** If changing the `.env` file does not change the settings, try restarting your shell or clearing the environment variables.

##### Settings

|Key|Description|Default value|
| --- | --- | --- |
|VID_OUTPUT_PXL_FORMAT|The pixel format for the video output|yuvj444p|
