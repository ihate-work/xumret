/**
 * Response types for termux-camera-info and termux-camera-photo.
 *
 * Source of truth: CameraInfoAPI.java in vendor/termux-api.
 * Fields that map Android enum constants use string | number because
 * unrecognised values fall through as raw integers in the JSON.
 */

/** Width × height pair (pixels for JPEG sizes, mm for physical sensor size). */
export interface Size {
  width: number;
  height: number;
}

/** Known values for CameraCharacteristics.LENS_FACING. */
export type CameraFacing = 'front' | 'back';

/** Known CONTROL_AE_MODE_* constants. */
export type AutoExposureMode =
  | 'CONTROL_AE_MODE_OFF'
  | 'CONTROL_AE_MODE_ON'
  | 'CONTROL_AE_MODE_ON_ALWAYS_FLASH'
  | 'CONTROL_AE_MODE_ON_AUTO_FLASH'
  | 'CONTROL_AE_MODE_ON_AUTO_FLASH_REDEYE'
  | 'CONTROL_AE_MODE_ON_EXTERNAL_FLASH';

/** Known REQUEST_AVAILABLE_CAPABILITIES_* constants. */
export type CameraCapability =
  | 'backward_compatible'
  | 'burst_capture'
  | 'constrained_high_speed_video'
  | 'depth_output'
  | 'logical_multi_camera'
  | 'manual_post_processing'
  | 'manual_sensor'
  | 'monochrome'
  | 'motion_tracking'
  | 'private_reprocessing'
  | 'raw'
  | 'read_sensor_settings'
  | 'yuv_reprocessing';

/** Single camera entry returned by termux-camera-info. */
export interface CameraInfo {
  id: string;
  facing: CameraFacing | number;
  jpeg_output_sizes: Size[];
  focal_lengths: number[];
  auto_exposure_modes: (AutoExposureMode | number)[];
  physical_size: Size;
  capabilities: (CameraCapability | number)[];
}

/** termux-camera-info returns an array of CameraInfo. */
export type CameraInfoResponse = CameraInfo[];

/**
 * termux-camera-photo writes a JPEG file to the device filesystem.
 * No JSON output on stdout — success/failure is indicated by exit code.
 */
