<template>
  <view class="page">
    <view class="hero">
      <text class="hero-title">视频去字幕</text>
      <text class="hero-sub">粘贴视频链接，在画面上框选字幕区域，一键去除</text>
    </view>

    <view class="panel">
      <text class="section-title">1. 粘贴视频链接</text>
      <textarea
        v-model="link"
        class="link-input"
        placeholder="粘贴视频直链（mp4/mov）或作品分享链接"
        :maxlength="-1"
        auto-height
        :disabled="submitting"
        @input="onLinkInput"
      />
      <button class="secondary-button" :disabled="loadingFrame || !link" @tap="loadFrame">
        {{ loadingFrame ? "正在读取视频..." : "读取视频并获取预览帧" }}
      </button>
      <text v-if="frameMessage" class="hint">{{ frameMessage }}</text>
    </view>

    <view v-if="frameUrl" class="panel">
      <view class="status-row">
        <text class="section-title">2. 框选字幕区域</text>
        <text v-if="frameInfo" class="badge">{{ frameInfo.width }} × {{ frameInfo.height }}</text>
      </view>
      <text class="hint">在画面上按住并拖动，框出字幕所在的位置</text>

      <view
        class="frame-wrap"
        @touchstart="onTouchStart"
        @touchmove.stop="onTouchMove"
        @touchend="onTouchEnd"
      >
        <image class="frame-canvas" :src="frameUrl" mode="widthFix" @load="onFrameLoad" />
        <view v-if="box" class="box-overlay" :style="boxStyle">
          <view class="box-corner tl" />
          <view class="box-corner tr" />
          <view class="box-corner bl" />
          <view class="box-corner br" />
        </view>
      </view>

      <view class="box-actions">
        <text class="box-tip">{{ box ? "已框选字幕区域" : "尚未框选，可先直接开始（默认处理底部）" }}</text>
        <button v-if="box" class="link-button" @tap="resetBox">重新框选</button>
      </view>
    </view>

    <view v-if="frameUrl" class="panel">
      <text class="section-title">3. 去除方式</text>
      <view class="tabs">
        <button
          v-for="option in methodOptions"
          :key="option.value"
          class="tab"
          :class="{ active: method === option.value }"
          @tap="method = option.value"
        >
          {{ option.label }}
        </button>
      </view>
      <text class="hint">{{ methodHint }}</text>

      <button class="primary-button" :disabled="submitting || !link" @tap="submit">
        {{ submitting ? "处理中，请稍候..." : "开始去字幕" }}
      </button>
    </view>

    <view v-if="task" class="panel">
      <view class="status-row">
        <text class="section-title">任务状态</text>
        <text class="badge">{{ statusLabel }}</text>
      </view>
      <progress :percent="task.progress" stroke-width="6" active />
      <text v-if="task.error_message" class="error">{{ task.error_message }}</text>
    </view>

    <view v-if="result" class="panel">
      <text class="section-title">处理结果</text>
      <text class="message">{{ result.message || "处理完成" }}</text>

      <view v-if="result.preview_url" class="result-block">
        <text class="key">字幕区域示意</text>
        <image class="preview-image" :src="toAbsoluteUrl(result.preview_url)" mode="widthFix" />
      </view>

      <view v-if="processedUrl" class="result-block highlight">
        <text class="key">处理后的视频</text>
        <video class="preview-video" :src="processedUrl" object-fit="contain" :controls="true" />
        <button class="download-button" @tap="saveToAlbum">保存到手机相册</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import { API_BASE_URL, createSubtitleRemoveTask, fetchSubtitleFrame, pollTask } from "../../services/api";
import type { SubtitleBox, SubtitleFrameInfo, TaskResponse, VideoSubtitleResult } from "../../types/task";

type Method = "delogo" | "inpaint";

const methodOptions: Array<{ label: string; value: Method }> = [
  { label: "快速（推荐）", value: "delogo" },
  { label: "精细（较慢）", value: "inpaint" },
];

const method = ref<Method>("delogo");
const link = ref("");
const loadingFrame = ref(false);
const submitting = ref(false);

const frameInfo = ref<SubtitleFrameInfo | null>(null);
const frameMessage = ref("");
const drawing = ref(false);
const box = ref<SubtitleBox | null>(null);
const startPoint = ref({ x: 0, y: 0 });
const frameRect = ref<{ left: number; top: number; width: number; height: number } | null>(null);

const task = ref<TaskResponse | null>(null);

const frameUrl = computed(() => {
  const info = frameInfo.value;
  if (!info || info.status !== "success" || !info.frame_url) {
    return "";
  }
  return toAbsoluteUrl(info.frame_url);
});

const methodHint = computed(() =>
  method.value === "delogo"
    ? "用周围画面插值填补字幕区域，速度快，适合多数场景"
    : "逐帧修复字幕区域，背景复杂时更自然，耗时更久"
);

const result = computed(() => {
  if (task.value?.status !== "success") {
    return null;
  }
  return task.value.result_payload as VideoSubtitleResult;
});

const statusLabel = computed(() => {
  if (!task.value) {
    return "";
  }
  const labels: Record<string, string> = {
    pending: "排队中",
    running: "处理中",
    success: "完成",
    failed: "失败",
    cancelled: "已取消",
  };
  return `${labels[task.value.status] ?? task.value.status} · ${task.value.progress}%`;
});

const processedUrl = computed(() => {
  const target = result.value?.processed_video_url || result.value?.download_url || "";
  return target ? toAbsoluteUrl(target) : "";
});

const boxStyle = computed(() => {
  if (!box.value) {
    return {};
  }
  const b = box.value;
  return {
    left: `${b.x * 100}%`,
    top: `${b.y * 100}%`,
    width: `${b.w * 100}%`,
    height: `${b.h * 100}%`,
  };
});

function onLinkInput() {
  // 链接变化后旧帧与旧结果失效
  frameInfo.value = null;
  frameMessage.value = "";
  box.value = null;
  task.value = null;
}

async function loadFrame() {
  const url = link.value.trim();
  if (!url) {
    return;
  }
  loadingFrame.value = true;
  frameInfo.value = null;
  box.value = null;
  task.value = null;
  frameMessage.value = "正在下载视频并抽取预览帧，请稍候...";
  try {
    const info = await fetchSubtitleFrame(url);
    frameInfo.value = info;
    if (info.status === "success") {
      frameMessage.value = "预览帧已就绪，请在下方框选字幕区域";
    } else {
      frameMessage.value = info.message || "视频读取失败，请检查链接后重试";
    }
  } catch (error) {
    frameMessage.value = error instanceof Error ? error.message : "视频读取失败";
    showError(error);
  } finally {
    loadingFrame.value = false;
  }
}

async function refreshFrameRect() {
  const rect = await getFrameRect();
  if (rect) {
    frameRect.value = rect;
  }
}

function onFrameLoad() {
  void refreshFrameRect();
}

async function onTouchStart(event: TouchEvent) {
  await refreshFrameRect();
  const normalized = touchToNormalized(event);
  if (!normalized) {
    return;
  }
  drawing.value = true;
  startPoint.value = normalized;
  box.value = { x: normalized.x, y: normalized.y, w: 0, h: 0 };
}

function onTouchMove(event: TouchEvent) {
  if (!drawing.value) {
    return;
  }
  const normalized = touchToNormalized(event);
  if (!normalized) {
    return;
  }
  const start = startPoint.value;
  box.value = {
    x: Math.min(start.x, normalized.x),
    y: Math.min(start.y, normalized.y),
    w: Math.abs(normalized.x - start.x),
    h: Math.abs(normalized.y - start.y),
  };
}

function onTouchEnd() {
  if (!drawing.value) {
    return;
  }
  drawing.value = false;
  const current = box.value;
  if (!current || current.w < 0.03 || current.h < 0.015) {
    box.value = null;
  }
}

function resetBox() {
  box.value = null;
}

async function submit() {
  const url = link.value.trim();
  if (!url) {
    return;
  }
  if (!box.value) {
    uni.showModal({
      title: "尚未框选字幕区域",
      content: "未框选时将默认处理画面底部 12% 的区域，是否继续？",
      success: (res) => {
        if (res.confirm) {
          void runRemove(url);
        }
      },
    });
    return;
  }
  await runRemove(url);
}

async function runRemove(url: string) {
  submitting.value = true;
  task.value = null;
  uni.showLoading({ title: "提交中...", mask: true });
  try {
    const created = await createSubtitleRemoveTask({
      url,
      method: method.value,
      region: box.value ?? { x: 0, y: 0.88, w: 1, h: 0.12 },
    });
    uni.hideLoading();
    task.value = created;
    uni.showLoading({ title: "处理中...", mask: true });
    task.value = await pollTask(created.id, { intervalMs: 2000, timeoutMs: 600000 });
  } catch (error) {
    showError(error);
  } finally {
    uni.hideLoading();
    submitting.value = false;
  }
}

function saveToAlbum() {
  if (!processedUrl.value) {
    showError(new Error("暂无可保存的视频"));
    return;
  }

  uni.showLoading({ title: "下载中...", mask: true });
  uni.downloadFile({
    url: processedUrl.value,
    success: (response) => {
      uni.hideLoading();
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
    fail: () => {
      uni.hideLoading();
      showError(new Error("视频下载失败"));
    },
  });
}

function getFrameRect(): Promise<{ left: number; top: number; width: number; height: number } | null> {
  return new Promise((resolve) => {
    uni
      .createSelectorQuery()
      .select(".frame-wrap")
      .boundingClientRect((rect) => {
        const info = rect as unknown as { left?: number; top?: number; width?: number; height?: number };
        if (!info || !info.width) {
          resolve(null);
          return;
        }
        resolve({
          left: info.left ?? 0,
          top: info.top ?? 0,
          width: info.width,
          height: info.height ?? 0,
        });
      })
      .exec();
  });
}

function touchToNormalized(event: TouchEvent): { x: number; y: number } | null {
  const rect = frameRect.value;
  const touch = event.touches?.[0] ?? event.changedTouches?.[0];
  if (!rect || !touch) {
    return null;
  }
  const clientX = touch.clientX;
  const clientY = touch.clientY;
  return {
    x: clamp((clientX - rect.left) / rect.width),
    y: clamp((clientY - rect.top) / rect.height),
  };
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
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

.hero {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-bottom: 24rpx;
  padding: 34rpx 30rpx;
  border-radius: 26rpx;
  color: #fff;
  background: linear-gradient(135deg, #0ea5e9, #14b8a6);
}

.hero-title {
  font-size: 38rpx;
  font-weight: 700;
}

.hero-sub {
  font-size: 26rpx;
  line-height: 1.5;
  opacity: 0.92;
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

.hint {
  color: #667085;
  font-size: 24rpx;
  line-height: 1.5;
}

.link-input {
  width: 100%;
  box-sizing: border-box;
  min-height: 96rpx;
  padding: 20rpx;
  border-radius: 16rpx;
  background: #f1f5f9;
  color: #172033;
  font-size: 26rpx;
  line-height: 1.5;
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
.secondary-button::after,
.download-button::after,
.link-button::after {
  border: 0;
}

.tab.active {
  color: #fff;
  background: #0ea5e9;
}

.secondary-button {
  border-radius: 999rpx;
  color: #0e7490;
  background: #ecfeff;
}

.secondary-button[disabled] {
  color: #94a3b8;
  background: #f1f5f9;
}

.primary-button {
  border-radius: 999rpx;
  color: #fff;
  background: #0ea5e9;
}

.primary-button[disabled] {
  color: #fff;
  background: #a5d8ea;
}

.frame-wrap {
  position: relative;
  width: 100%;
  border-radius: 16rpx;
  overflow: hidden;
  background: #000;
}

.frame-canvas {
  display: block;
  width: 100%;
}

.box-overlay {
  position: absolute;
  box-sizing: border-box;
  border: 3rpx solid #22d3ee;
  background: rgba(34, 211, 238, 0.18);
}

.box-corner {
  position: absolute;
  width: 22rpx;
  height: 22rpx;
  border: 4rpx solid #22d3ee;
}

.box-corner.tl {
  top: -4rpx;
  left: -4rpx;
  border-right: 0;
  border-bottom: 0;
}

.box-corner.tr {
  top: -4rpx;
  right: -4rpx;
  border-left: 0;
  border-bottom: 0;
}

.box-corner.bl {
  bottom: -4rpx;
  left: -4rpx;
  border-right: 0;
  border-top: 0;
}

.box-corner.br {
  bottom: -4rpx;
  right: -4rpx;
  border-left: 0;
  border-top: 0;
}

.box-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}

.box-tip {
  color: #667085;
  font-size: 24rpx;
}

.link-button {
  margin: 0;
  padding: 0 24rpx;
  border-radius: 999rpx;
  color: #0e7490;
  background: #ecfeff;
  font-size: 24rpx;
}

.preview-video {
  width: 100%;
  height: 460rpx;
  border-radius: 16rpx;
  background: #000;
}

.preview-image {
  width: 100%;
  border-radius: 16rpx;
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
  color: #0e7490;
  background: #ecfeff;
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
  gap: 12rpx;
}

.highlight {
  padding: 20rpx;
  border-radius: 16rpx;
  background: #f8fafc;
}

.download-button {
  align-self: flex-start;
  margin-top: 4rpx;
  padding: 0 28rpx;
  border-radius: 999rpx;
  color: #0e7490;
  background: #ecfeff;
  font-size: 25rpx;
}

.error {
  color: #dc2626;
  font-size: 26rpx;
}
</style>
