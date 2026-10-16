export type TaskType =
  | "link_parse"
  | "remove_watermark"
  | "video_watermark"
  | "remove_subtitle"
  | "ocr_extract"
  | "video_generate";

export type TaskStatus = "pending" | "running" | "success" | "failed" | "cancelled";

export interface TaskResponse {
  id: string;
  type: TaskType;
  status: TaskStatus;
  progress: number;
  input_payload: Record<string, unknown>;
  result_payload: Record<string, unknown>;
  error_code?: string | null;
  error_message?: string | null;
}

export interface LinkAsset {
  type: "video" | "image";
  source_url: string;
  local_url: string;
  mime_type: string;
  width?: number | null;
  height?: number | null;
}

export interface LinkParseResult {
  platform?: string;
  source_url?: string;
  media_type?: "video" | "image" | "mixed" | "unknown";
  caption?: string | null;
  speech_text?: string | null;
  speech_status?: "success" | "empty" | "skipped" | "failed";
  speech_message?: string | null;
  title?: string | null;
  author?: string | null;
  cover_url?: string | null;
  assets?: LinkAsset[];
  parse_method?: string;
  download_status?: "success" | "empty";
}

export interface FileProcessResult {
  message?: string;
  method?: string;
  text?: string;
  video_text?: string;
  download_url?: string;
  processed_video_url?: string;
  source?: Record<string, unknown>;
}

export interface WatermarkRegion {
  x: number;
  y: number;
  w: number;
  h: number;
  confidence: number;
  source: string;
}

export interface VideoMeta {
  width?: number;
  height?: number;
  fps?: number;
  frame_count?: number;
  duration?: number;
}

export interface VideoWatermarkResult extends FileProcessResult {
  status?: "success" | "unsupported" | "failed";
  mode?: "auto" | "manual";
  algorithm?: "delogo" | "inpaint";
  regions?: WatermarkRegion[];
  detected_regions?: WatermarkRegion[];
  video_meta?: VideoMeta;
  original_video_url?: string;
  preview_url?: string;
}

export interface VideoGenerateResult {
  message?: string;
  template_id?: string;
  source?: Record<string, unknown>;
}

export interface SubtitleFrameInfo {
  status: "success" | "unavailable" | string;
  message?: string;
  frame_url?: string;
  width?: number;
  height?: number;
  duration?: number;
  download_url?: string;
}

export interface VideoSubtitleResult extends FileProcessResult {
  status?: "success" | "failed";
  algorithm?: "delogo" | "inpaint";
  regions?: WatermarkRegion[];
  video_meta?: VideoMeta;
  original_video_url?: string;
  preview_url?: string;
}

export interface SubtitleBox {
  x: number;
  y: number;
  w: number;
  h: number;
}
