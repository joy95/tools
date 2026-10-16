import type { SubtitleBox, SubtitleFrameInfo, TaskResponse, TaskType } from "../types/task";

export const API_BASE_URL = __API_BASE_URL__;
export const DEFAULT_USER_ID = "anonymous";

type RequestMethod = "GET" | "POST" | "PUT" | "DELETE";

interface RequestOptions<TData = unknown> {
  url: string;
  method?: RequestMethod;
  data?: TData;
}

export function request<TResponse, TData = unknown>(options: RequestOptions<TData>): Promise<TResponse> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE_URL}${options.url}`,
      method: options.method ?? "GET",
      data: options.data as Record<string, unknown> | undefined,
      header: {
        "content-type": "application/json",
      },
      success: (response) => {
        const statusCode = response.statusCode ?? 0;
        if (statusCode >= 200 && statusCode < 300) {
          resolve(response.data as TResponse);
          return;
        }
        reject(new Error(extractErrorMessage(response.data) || `请求失败：${statusCode}`));
      },
      fail: (error) => reject(new Error(error.errMsg || "网络请求失败")),
    });
  });
}

export function createLinkParseTask(url: string, rawText = ""): Promise<TaskResponse> {
  return request<TaskResponse>({
    url: "/api/tasks/link-parse",
    method: "POST",
    data: {
      url,
      raw_text: rawText,
      user_id: DEFAULT_USER_ID,
    },
  });
}

export function createVideoGenerateTask(payload: {
  image_asset_ids: string[];
  text: string;
  template_id: string;
}): Promise<TaskResponse> {
  return request<TaskResponse>({
    url: "/api/tasks/video-generate",
    method: "POST",
    data: {
      ...payload,
      user_id: DEFAULT_USER_ID,
    },
  });
}

export function getTask(taskId: string): Promise<TaskResponse> {
  return request<TaskResponse>({
    url: `/api/tasks/${taskId}`,
  });
}

export function listTasks(): Promise<TaskResponse[]> {
  return request<TaskResponse[]>({
    url: `/api/tasks?user_id=${encodeURIComponent(DEFAULT_USER_ID)}`,
  });
}

export function uploadTaskFile(filePath: string, processType: Extract<TaskType, "remove_watermark" | "remove_subtitle" | "ocr_extract">): Promise<TaskResponse> {
  return uploadFileTask(`${API_BASE_URL}/api/tasks/file-process`, filePath, {
    process_type: processType,
    user_id: DEFAULT_USER_ID,
  });
}

export interface VideoWatermarkOptions {
  mode: "auto" | "manual";
  region?: string;
  size?: "small" | "medium" | "large";
  method?: "delogo" | "inpaint";
}

export function uploadVideoWatermark(filePath: string, options: VideoWatermarkOptions): Promise<TaskResponse> {
  return uploadFileTask(`${API_BASE_URL}/api/tasks/video-watermark`, filePath, {
    user_id: DEFAULT_USER_ID,
    mode: options.mode,
    region: options.region ?? "",
    size: options.size ?? "medium",
    method: options.method ?? "delogo",
  });
}

export function fetchSubtitleFrame(url: string): Promise<SubtitleFrameInfo> {
  return request<SubtitleFrameInfo>({
    url: "/api/tasks/subtitle/frame",
    method: "POST",
    data: {
      url,
      user_id: DEFAULT_USER_ID,
    },
  });
}

export function createSubtitleRemoveTask(payload: {
  url: string;
  method?: "delogo" | "inpaint";
  region: SubtitleBox;
}): Promise<TaskResponse> {
  return request<TaskResponse>({
    url: "/api/tasks/subtitle/remove",
    method: "POST",
    data: {
      url: payload.url,
      method: payload.method ?? "delogo",
      region: payload.region,
      user_id: DEFAULT_USER_ID,
    },
  });
}

function uploadFileTask(url: string, filePath: string, formData: Record<string, string>): Promise<TaskResponse> {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url,
      filePath,
      name: "file",
      formData,
      success: (response) => {
        const statusCode = response.statusCode ?? 0;
        const data = parseUploadResponse(response.data);
        if (statusCode >= 200 && statusCode < 300) {
          resolve(data as TaskResponse);
          return;
        }
        reject(new Error(extractErrorMessage(data) || `上传失败：${statusCode}`));
      },
      fail: (error) => reject(new Error(error.errMsg || "文件上传失败")),
    });
  });
}

export async function pollTask(taskId: string, options?: { intervalMs?: number; timeoutMs?: number }): Promise<TaskResponse> {
  const intervalMs = options?.intervalMs ?? 1200;
  const timeoutMs = options?.timeoutMs ?? 30000;
  const startedAt = Date.now();

  while (Date.now() - startedAt <= timeoutMs) {
    const task = await getTask(taskId);
    if (task.status === "success" || task.status === "failed" || task.status === "cancelled") {
      return task;
    }
    await delay(intervalMs);
  }

  throw new Error("任务处理超时，请稍后在任务列表查看结果");
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseUploadResponse(data: string): unknown {
  try {
    return JSON.parse(data);
  } catch {
    return data;
  }
}

function extractErrorMessage(data: unknown): string {
  if (typeof data === "string") {
    return data;
  }
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail;
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  }
  return "";
}
