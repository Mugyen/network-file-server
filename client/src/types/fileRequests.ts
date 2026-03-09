/** File request status values matching server RequestStatus enum. */
export const RequestStatus = {
  PENDING: "pending",
  FULFILLED: "fulfilled",
  DISMISSED: "dismissed",
} as const;

export type RequestStatus = (typeof RequestStatus)[keyof typeof RequestStatus];

/** A file request created by one device for others to fulfill. */
export interface FileRequest {
  id: string;
  description: string;
  requester_device_id: string;
  requester_device_name: string;
  status: RequestStatus;
  created_at: string;
  fulfilled_by_device_name: string | null;
  fulfilled_file_name: string | null;
  fulfilled_file_path: string | null;
  fulfilled_at: string | null;
}
