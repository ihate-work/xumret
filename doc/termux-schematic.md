# Termux API Schematic

## termux-api

Android app that exposes Android system APIs to command-line usage within Termux.

### Architecture

**Communication Protocol:**

- Uses Linux anonymous namespace sockets for IPC
- CLI binary creates 2 sockets (input + output) and passes addresses via `am broadcast`
- Bidirectional data flow through sockets between CLI and API handlers

**Key Components:**

- `TermuxApiReceiver` - Broadcast receiver that routes API requests to handlers
- `SocketListener` - Background thread accepting socket connections, parsing CLI args
- `ResultReturner` - Handles socket I/O for returning data to CLI
- API handlers in `com.termux.api.apis.*` - One class per API (37 total)

### Command Flow

```
CLI binary (termux-api)
    → Creates 2 Unix sockets
    → am broadcast com.termux.api.TermuxApiReceiver
        --es api_method <METHOD>
        --es socket_input <addr>
        --es socket_output <addr>
    → TermuxApiReceiver.onReceive()
        → Routes to API handler via switch on "api_method"
    → API handler
        → Accesses Android system services
        → ResultReturner writes to output socket
    → CLI reads output socket → stdout
```

### ResultWriter Patterns

| Pattern            | Use Case                  | Example                  |
| ------------------ | ------------------------- | ------------------------ |
| `ResultWriter`     | Plain text output         | Basic status             |
| `ResultJsonWriter` | JSON output               | `BatteryStatusAPI`       |
| `WithStringInput`  | Read stdin, return result | `ToastAPI`, `SmsSendAPI` |
| `BinaryOutput`     | Raw binary data           | `CameraPhotoAPI`         |
| `WithAncillaryFd`  | Pass file descriptors     | Storage APIs             |

### Available APIs (37)

| Category      | APIs                                                                                                                                                              |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Audio/Media   | AudioInfo, Volume, MicRecorder, MediaPlayer, TextToSpeech, SpeechToText                                                                                           |
| Communication | SmsInbox, SmsSend, CallLog, TelephonyCall, TelephonyDeviceInfo, Clipboard, Share                                                                                  |
| Sensors       | Location, Sensor (accelerometer, gyroscope, etc.)                                                                                                                 |
| Camera        | CameraInfo, CameraPhoto                                                                                                                                           |
| Network       | WifiConnectionInfo, WifiScanInfo, WifiEnable, Nfc                                                                                                                 |
| Hardware      | Torch, Vibrate, InfraredFrequencies, InfraredTransmit, Usb, Fingerprint                                                                                           |
| System        | BatteryStatus, ContactList, Notification, NotificationList, JobScheduler, StorageGet, SAF, MediaScanner, Dialog, Toast, Wallpaper, Brightness, Keystore, Download |

### Security Model

- Shares UID with main Termux app (`sharedUserId`)
- UID validation in SocketListener - only Termux processes can invoke APIs
- Runtime permission checks for sensitive operations
- Must be signed with same key as Termux

### Key Files

- `app/src/main/java/com/termux/api/TermuxApiReceiver.java` - Main dispatcher
- `app/src/main/java/com/termux/api/SocketListener.java` - Socket communication
- `app/src/main/java/com/termux/api/util/ResultReturner.java` - Result output handling
- `app/src/main/java/com/termux/api/apis/*.java` - Individual API implementations
- `app/src/main/AndroidManifest.xml` - Permissions and component declarations

## termux-api-package

CLI scripts/binaries that users invoke from Termux shell. Lives in separate repository.

### Structure

- Contains shell scripts and C binary (`termux-api.c`)
- Each command (e.g., `termux-battery-status`, `termux-vibrate`) is a wrapper
- Handles argument parsing before communicating with the Android app

### How CLI Commands Work

1. User invokes command (e.g., `termux-vibrate -d 500`)
2. CLI parses arguments into Intent extras format
3. Creates 2 Unix sockets for bidirectional communication
4. Sends broadcast to `TermuxApiReceiver` with socket addresses
5. Reads response from output socket
6. Prints result to stdout

### Intent Extra Formats (parsed by SocketListener)

| Flag                  | Type       | Example                         |
| --------------------- | ---------- | ------------------------------- |
| `-e`, `--es`, `--esa` | String     | `--es api_method BatteryStatus` |
| `--ez`                | Boolean    | `--ez short true`               |
| `--ei`                | Integer    | `--ei duration_ms 500`          |
| `--ef`                | Float      | `--ef volume 0.5`               |
| `--eia`               | Int array  | `--eia values 1,2,3`            |
| `--ela`               | Long array | `--ela timestamps 123,456`      |
