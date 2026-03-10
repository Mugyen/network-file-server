export interface ServerInfo {
  ip: string;
  port: number;
  url: string;
  qr_svg: string;
  all_ips: string[];
  read_only: boolean;
  receive: boolean;
  password_required: boolean;
  hostname: string;
}
