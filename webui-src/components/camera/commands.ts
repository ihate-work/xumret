import type { PhoneCommandInput } from '~/_api';

/** termux-camera-info — list available cameras and their capabilities. */
export function cameraInfo(): PhoneCommandInput {
  return {
    name: 'camera-info',
    steps: [{ argv: ['termux-camera-info'] }],
  };
}

/** termux-camera-photo — capture a JPEG image to a file on the device.
 * @param outputPath absolute path on the phone for the JPEG output
 * @param cameraId camera to use (from CameraInfo.id), default "0" (back)
 */
export function cameraPhoto(outputPath: string, cameraId = '0'): PhoneCommandInput {
  return {
    name: 'camera-photo',
    steps: [{ argv: ['termux-camera-photo', '-c', cameraId, outputPath] }],
  };
}
