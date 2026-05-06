# Use cases

Each use case is a policy the WebUI implements on top of the generic command mechanism.
The `termux-*` names refer to termux-api CLI commands.

## Read SMS

`termux-sms-list`

## Send SMS

`termux-sms-send`

## Get phone state (battery, location, wifi, telephony, ...)

`termux-battery-status`, `termux-location`, `termux-wifi-connectioninfo`, `termux-wifi-scaninfo`, `termux-telephony-deviceinfo`, `termux-telephony-cellinfo`

## Get camera spec

`termux-camera-info`

## Take photo

`termux-camera-photo`

## Take video

`termux-microphone-record`, `termux-camera-photo` (repeated capture — no native video command in termux-api)

## Stream video

`termux-camera-photo` (continuous capture + push to UI via SSE or polling)

---

## Future

### Clipboard

`termux-clipboard-get`, `termux-clipboard-set`

### Notifications

`termux-notification`, `termux-notification-list`, `termux-notification-remove`, `termux-notification-channel`

### Contacts & call log

`termux-contact-list`, `termux-call-log`, `termux-telephony-call`

### Audio

`termux-audio-info`, `termux-media-player`, `termux-microphone-record`

### Text-to-speech / speech-to-text

`termux-tts-engines`, `termux-tts-speak`, `termux-speech-to-text`

### Dialog (interactive prompts on phone)

`termux-dialog`

### Sensors

`termux-sensor`

### Device controls

`termux-torch`, `termux-vibrate`, `termux-volume`, `termux-brightness`, `termux-wallpaper`

### File access (SAF)

`termux-saf-create`, `termux-saf-dirs`, `termux-saf-ls`, `termux-saf-managedir`, `termux-saf-mkdir`, `termux-saf-read`, `termux-saf-rm`, `termux-saf-stat`, `termux-saf-write`

### Sharing & downloads

`termux-share`, `termux-download`, `termux-storage-get`, `termux-media-scan`

### Hardware

`termux-fingerprint`, `termux-infrared-frequencies`, `termux-infrared-transmit`, `termux-nfc`, `termux-usb`

### System

`termux-toast`, `termux-job-scheduler`, `termux-keystore`, `termux-wifi-enable`
