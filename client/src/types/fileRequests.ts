/**
 * File-request types. FileRequest is derived from the server's OpenAPI schema;
 * the RequestStatus runtime const is kept here for value comparisons.
 */
import type { Schemas } from "./api.ts";

/** File request status values matching server RequestStatus enum. */
export const RequestStatus = {
  PENDING: "pending",
  FULFILLED: "fulfilled",
  DISMISSED: "dismissed",
} as const;

export type RequestStatus = (typeof RequestStatus)[keyof typeof RequestStatus];

export type FileRequest = Schemas["FileRequest"];
