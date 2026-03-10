/** WebSocket message types matching server WSMessageType enum. */
export const WSMessageType = {
  TOAST: "toast",
  SNIPPET_UPDATED: "snippet_updated",
  SNIPPET_CREATED: "snippet_created",
  SNIPPET_DELETED: "snippet_deleted",
  REQUEST_CREATED: "request_created",
  REQUEST_FULFILLED: "request_fulfilled",
  REQUEST_DISMISSED: "request_dismissed",
  DEVICE_COUNT: "device_count",
  SNIPPET_UPDATE: "snippet_update",
  DEVICE_LIST: "device_list",
} as const;

export type WSMessageType = (typeof WSMessageType)[keyof typeof WSMessageType];

/** Toast notification types matching server ToastType enum. */
export const ToastType = {
  FILE_UPLOADED: "file_uploaded",
  DEVICE_CONNECTED: "device_connected",
  DEVICE_DISCONNECTED: "device_disconnected",
  REQUEST_CREATED: "request_created",
  REQUEST_FULFILLED: "request_fulfilled",
} as const;

export type ToastType = (typeof ToastType)[keyof typeof ToastType];

export interface ToastMessage {
  id: string;
  toastType: ToastType;
  message: string;
  deviceName: string;
  timestamp: string;
}

export interface WSToastPayload {
  type: typeof WSMessageType.TOAST;
  toast_type: ToastType;
  message: string;
  device_name: string;
  timestamp: string;
}

export interface WSDeviceCountPayload {
  type: typeof WSMessageType.DEVICE_COUNT;
  count: number;
}

/** Device type enum matching server DeviceType. */
export const DeviceType = {
  PHONE: "phone",
  TABLET: "tablet",
  DESKTOP: "desktop",
} as const;

export type DeviceType = (typeof DeviceType)[keyof typeof DeviceType];

/** Information about a connected device. */
export interface DeviceInfo {
  device_id: string;
  device_name: string;
  ip_address: string;
  device_type: DeviceType;
  connected_at: string;
}

export interface WSDeviceListPayload {
  type: typeof WSMessageType.DEVICE_LIST;
  devices: DeviceInfo[];
  your_device_id: string;
}

/** Extensible union for all WS message types (future plans add more). */
export type WSMessage =
  | WSToastPayload
  | WSDeviceCountPayload
  | WSDeviceListPayload
  | { type: string; [key: string]: unknown };

const ADJECTIVES = [
  "Swift", "Brave", "Calm", "Eager", "Gentle", "Happy", "Keen", "Lively",
  "Neat", "Proud", "Quick", "Smart", "Warm", "Zesty", "Bold", "Crisp",
  "Deft", "Fair", "Grand", "Jolly", "Kind", "Mild", "Noble", "Pure",
  "Rich", "Sage", "True", "Vast", "Wise", "Zen",
];

const ANIMALS = [
  "Fox", "Owl", "Bear", "Deer", "Wolf", "Hawk", "Lynx", "Puma",
  "Swan", "Wren", "Seal", "Hare", "Dove", "Crab", "Frog", "Moth",
  "Newt", "Pike", "Toad", "Wasp", "Yak", "Crow", "Duck", "Goat",
  "Ibis", "Kiwi", "Lark", "Mole", "Orca", "Pika",
];

const DEVICE_NAME_KEY = "wfs_device_name";

function generateDeviceName(): string {
  const adj = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)];
  const animal = ANIMALS[Math.floor(Math.random() * ANIMALS.length)];
  return `${adj} ${animal}`;
}

/** Get a stable device name from localStorage, generating one if absent. */
export function getDeviceName(): string {
  const stored = localStorage.getItem(DEVICE_NAME_KEY);
  if (stored !== null) {
    return stored;
  }
  const name = generateDeviceName();
  localStorage.setItem(DEVICE_NAME_KEY, name);
  return name;
}
