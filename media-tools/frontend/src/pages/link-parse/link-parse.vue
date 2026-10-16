<template>
  <view class="page">
    <view class="panel">
      <view class="input-wrap">
        <textarea v-model="url" class="textarea" placeholder="请输入短视频分享链接地址" />
        <button class="input-action" @tap.stop="pasteOrClear">{{ url.trim() ? "清空" : "粘贴" }}</button>
      </view>
      <button class="primary-button" :disabled="submitting || !url.trim()" @tap="submit">
        {{ submitting ? "解析中..." : "立即解析" }}
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
      <text class="section-title">解析结果</text>
      <view class="result-block highlight">
        <text class="key">作品文案</text>
        <text class="value">{{ result.caption || "-" }}</text>
        <button v-if="result.caption" class="copy-button" @tap="copy(result.caption)">复制文案</button>
      </view>
      <view class="result-block highlight">
        <text class="key">口播文案</text>
        <text class="value">{{ speechDisplayText(result) }}</text>
        <button v-if="result.speech_text" class="copy-button" @tap="copy(result.speech_text)">复制口播文案</button>
      </view>
      <text class="key">媒体文件</text>
      <view class="media-list">
        <view v-for="item in result.assets || []" :key="item.local_url || item.source_url" class="media-item">
          <text>{{ item.type }}</text>
          <video v-if="item.type === 'video' && item.local_url" class="media-video" :src="toAbsoluteUrl(item.local_url)" controls />
          <text v-else class="media-url" @tap="copy(item.local_url)">{{ item.local_url }}</text>
          <button v-if="item.local_url" class="copy-button" @tap="downloadAsset(item)">下载到本地</button>
        </view>
        <text v-if="!(result.assets || []).length" class="value">-</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import { API_BASE_URL, createLinkParseTask, pollTask } from "../../services/api";
import type { LinkAsset, LinkParseResult, TaskResponse } from "../../types/task";

const url = ref("");
const submitting = ref(false);
const task = ref<TaskResponse | null>(null);

const result = computed(() => {
  if (task.value?.status !== "success") {
    return null;
  }
  return task.value.result_payload as LinkParseResult;
});

async function submit() {
  const parsedUrl = extractFirstUrl(url.value);
  if (!parsedUrl) {
    showError(new Error("请输入有效链接"));
    return;
  }

  submitting.value = true;
  task.value = null;
  try {
    const created = await createLinkParseTask(parsedUrl, url.value);
    task.value = created;
    task.value = await pollTask(created.id);
  } catch (error) {
    showError(error);
  } finally {
    submitting.value = false;
  }
}

function copy(text: string) {
  uni.setClipboardData({ data: text });
}

function speechDisplayText(result: LinkParseResult): string {
  if (result.speech_text) {
    return result.speech_text;
  }
  if (result.speech_status === "skipped") {
    return "当前作品无需提取口播文案";
  }
  if (result.speech_status === "failed") {
    return result.speech_message || "口播文案提取失败";
  }
  if (result.speech_status === "empty") {
    return result.speech_message || "未识别到有效口播内容";
  }
  return "-";
}

function pasteOrClear() {
  if (url.value.trim()) {
    url.value = "";
    return;
  }

  uni.getClipboardData({
    showToast: false,
    success: (response) => {
      url.value = response.data || "";
    },
    fail: () => showError(new Error("读取剪贴板失败")),
  });
}

function downloadAsset(asset: LinkAsset) {
  if (!asset.local_url) {
    showError(new Error("暂无可下载文件"));
    return;
  }

  const targetUrl = toAbsoluteUrl(asset.local_url);
  uni.downloadFile({
    url: targetUrl,
    success: (response) => {
      if (response.statusCode !== 200) {
        showError(new Error("下载失败"));
        return;
      }
      if (asset.type === "video") {
        uni.saveVideoToPhotosAlbum({
          filePath: response.tempFilePath,
          success: () => uni.showToast({ title: "已保存到相册", icon: "success" }),
          fail: () => showError(new Error("保存失败，请检查相册权限")),
        });
        return;
      }
      uni.saveImageToPhotosAlbum({
        filePath: response.tempFilePath,
        success: () => uni.showToast({ title: "已保存到相册", icon: "success" }),
        fail: () => showError(new Error("保存失败，请检查相册权限")),
      });
    },
    fail: () => showError(new Error("下载失败")),
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

function extractFirstUrl(text: string): string {
  const match = text.trim().match(/https?:\/\/[^\s，。；、]+/i);
  return match?.[0] ?? "";
}

function showError(error: unknown) {
  uni.showToast({
    title: error instanceof Error ? error.message : "解析失败",
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

.label,
.section-title {
  font-size: 30rpx;
  font-weight: 700;
  color: #172033;
}

.textarea {
  width: 100%;
  min-height: 180rpx;
  box-sizing: border-box;
  padding: 64rpx 20rpx 20rpx;
  border-radius: 18rpx;
  background: #f8fafc;
  font-size: 28rpx;
}

.input-wrap {
  position: relative;
}

.input-action {
  position: absolute;
  top: 16rpx;
  right: -10rpx;
  z-index: 1;
  height: 56rpx;
  line-height: 56rpx;
  padding: 0 22rpx;
  color: #fff;
  background: #2563eb;
  font-size: 24rpx;
}

.input-action::after {
  border: 0;
}

.hint {
  color: #667085;
  font-size: 24rpx;
}

.primary-button {
  border-radius: 999rpx;
  color: #fff;
  background: #2563eb;
}

.primary-button::after {
  border: 0;
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

.key {
  flex: none;
  color: #667085;
  font-size: 26rpx;
}

.value {
  color: #172033;
  font-size: 28rpx;
  line-height: 1.6;
}

.result-block {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.media-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.media-item {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  padding: 18rpx;
  border-radius: 16rpx;
  background: #f8fafc;
  font-size: 26rpx;
}

.media-url {
  color: #2563eb;
  word-break: break-all;
}

.media-video {
  width: 100%;
  border-radius: 12rpx;
}

.highlight {
  padding: 20rpx;
  border-radius: 16rpx;
  background: #f8fafc;
}

.copy-button {
  align-self: flex-start;
  margin-top: 8rpx;
  padding: 0 24rpx;
  border-radius: 999rpx;
  color: #2563eb;
  background: #eff6ff;
  font-size: 24rpx;
}

.copy-button::after {
  border: 0;
}

.error {
  color: #dc2626;
  font-size: 26rpx;
}
</style>
