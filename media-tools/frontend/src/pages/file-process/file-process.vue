<template>
  <view class="page">
    <view class="panel">
      <text class="section-title">处理类型</text>
      <view class="tabs">
        <button
          v-for="option in processOptions"
          :key="option.value"
          class="tab"
          :class="{ active: processType === option.value }"
          @tap="processType = option.value"
        >
          {{ option.label }}
        </button>
      </view>
    </view>

    <view class="panel">
      <text class="section-title">选择文件</text>
      <button class="secondary-button" @tap="chooseFile">选择图片/视频</button>
      <text v-if="filePath" class="file-path">{{ filePath }}</text>
      <button class="primary-button" :disabled="submitting || !filePath" @tap="submit">
        {{ submitting ? "处理中..." : "提交任务" }}
      </button>
    </view>

    <view v-if="task" class="panel">
      <view class="status-row">
        <text class="section-title">任务状态</text>
        <text class="badge">{{ task.status }} · {{ task.progress }}%</text>
      </view>
      <progress :percent="task.progress" stroke-width="6" active />
      <text v-if="task.error_message" class="error">{{ task.error_message }}</text>
    </view>

    <view v-if="result" class="panel">
      <text class="section-title">处理结果</text>
      <text class="message">{{ result.message || "处理完成" }}</text>
      <view v-if="result.method" class="result-line">
        <text class="key">处理方法</text>
        <text class="value">{{ result.method }}</text>
      </view>
      <view v-if="result.text !== undefined" class="result-block">
        <text class="key">OCR 文本</text>
        <text class="value">{{ result.text || "暂无识别文本" }}</text>
      </view>
      <view v-if="result.video_text !== undefined" class="result-block">
        <text class="key">视频中的文案</text>
        <text class="value">{{ result.video_text || "暂无识别文本" }}</text>
      </view>
      <view v-if="result.processed_video_url || result.download_url" class="result-block highlight">
        <text class="key">处理后视频</text>
        <text class="value">{{ result.processed_video_url || result.download_url }}</text>
        <button class="download-button" @tap="downloadVideo">下载到本地</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import { API_BASE_URL, pollTask, uploadTaskFile } from "../../services/api";
import type { FileProcessResult, TaskResponse, TaskType } from "../../types/task";

type FileProcessType = Extract<TaskType, "remove_watermark" | "remove_subtitle" | "ocr_extract">;

const processOptions: Array<{ label: string; value: FileProcessType }> = [
  { label: "去水印", value: "remove_watermark" },
  { label: "去字幕", value: "remove_subtitle" },
  { label: "OCR", value: "ocr_extract" },
];

const processType = ref<FileProcessType>("remove_watermark");
const filePath = ref("");
const submitting = ref(false);
const task = ref<TaskResponse | null>(null);

const result = computed(() => {
  if (task.value?.status !== "success") {
    return null;
  }
  return task.value.result_payload as FileProcessResult;
});

function chooseFile() {
  uni.chooseMedia({
    count: 1,
    mediaType: ["image", "video"],
    sourceType: ["album", "camera"],
    success: (response) => {
      const files = response.tempFiles as Array<{ tempFilePath: string }>;
      filePath.value = files[0]?.tempFilePath ?? "";
    },
    fail: (error) => {
      if (!error.errMsg.includes("cancel")) {
        showError(new Error(error.errMsg));
      }
    },
  });
}

async function submit() {
  if (!filePath.value) {
    return;
  }

  submitting.value = true;
  task.value = null;
  try {
    const created = await uploadTaskFile(filePath.value, processType.value);
    task.value = created;
    task.value = await pollTask(created.id);
  } catch (error) {
    showError(error);
  } finally {
    submitting.value = false;
  }
}

function downloadVideo() {
  const targetUrl = toAbsoluteUrl(result.value?.download_url || result.value?.processed_video_url || "");
  if (!targetUrl) {
    showError(new Error("暂无可下载视频"));
    return;
  }

  uni.downloadFile({
    url: targetUrl,
    success: (response) => {
      if (response.statusCode !== 200) {
        showError(new Error("视频下载失败"));
        return;
      }
      uni.saveVideoToPhotosAlbum({
        filePath: response.tempFilePath,
        success: () => uni.showToast({ title: "已保存到相册", icon: "success" }),
        fail: () => showError(new Error("保存失败，请检查相册权限")),
      });
    },
    fail: () => showError(new Error("视频下载失败")),
  });
}

function toAbsoluteUrl(value: string): string {
  if (!value) {
    return "";
  }
  if (value.startsWith("http://") || value.startsWith("https://")) {
    return value;
  }
  return `${API_BASE_URL}${value}`;
}

function showError(error: unknown) {
  uni.showToast({
    title: error instanceof Error ? error.message : "处理失败",
    icon: "none",
  });
}
</script>

<style scoped>
.page {
  padding: 28rpx;
}

.panel {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  margin-bottom: 24rpx;
  padding: 28rpx;
  border-radius: 24rpx;
  background: #fff;
}

.section-title {
  font-size: 30rpx;
  font-weight: 700;
  color: #172033;
}

.tabs {
  display: flex;
  gap: 16rpx;
}

.tab {
  flex: 1;
  border-radius: 999rpx;
  color: #475467;
  background: #f1f5f9;
  font-size: 26rpx;
}

.tab::after,
.primary-button::after,
.secondary-button::after {
  border: 0;
}

.tab.active {
  color: #fff;
  background: #2563eb;
}

.secondary-button {
  border-radius: 999rpx;
  color: #2563eb;
  background: #eff6ff;
}

.primary-button {
  border-radius: 999rpx;
  color: #fff;
  background: #16a34a;
}

.file-path {
  color: #667085;
  font-size: 24rpx;
  word-break: break-all;
}

.status-row,
.result-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}

.badge {
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  color: #2563eb;
  background: #eff6ff;
  font-size: 24rpx;
}

.message,
.value {
  color: #172033;
  font-size: 28rpx;
  line-height: 1.6;
}

.key {
  color: #667085;
  font-size: 26rpx;
}

.result-block {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.highlight {
  padding: 20rpx;
  border-radius: 16rpx;
  background: #f8fafc;
}

.download-button {
  align-self: flex-start;
  margin-top: 8rpx;
  padding: 0 24rpx;
  border-radius: 999rpx;
  color: #2563eb;
  background: #eff6ff;
  font-size: 24rpx;
}

.download-button::after {
  border: 0;
}

.error {
  color: #dc2626;
  font-size: 26rpx;
}
</style>
