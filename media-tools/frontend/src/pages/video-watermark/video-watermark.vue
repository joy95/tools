<template>
  <view class="page">
    <view class="hero">
      <text class="hero-title">视频去水印</text>
      <text class="hero-sub">上传本地视频，自动定位并去掉 AI 生成角标水印</text>
    </view>

    <view class="panel">
      <text class="section-title">1. 选择视频</text>
      <button class="secondary-button" @tap="chooseVideo">从相册选择</button>
      <video
        v-if="filePath"
        class="preview-video"
        :src="filePath"
        object-fit="contain"
        :controls="true"
      />
      <text v-if="fileLabel" class="file-label">{{ fileLabel }}</text>
    </view>

    <view class="panel">
      <text class="section-title">2. 水印位置</text>
      <view class="tabs">
        <button
          v-for="option in modeOptions"
          :key="option.value"
          class="tab"
          :class="{ active: mode === option.value }"
          @tap="mode = option.value"
        >
          {{ option.label }}
        </button>
      </view>
      <text class="hint">{{ modeHint }}</text>

      <template v-if="mode === 'manual'">
        <text class="field-label">水印在哪个位置</text>
        <view class="region-grid">
          <button
            v-for="option in regionOptions"
            :key="option.value"
            class="region-chip"
            :class="{ active: region === option.value }"
            @tap="region = option.value"
          >
            {{ option.label }}
          </button>
        </view>

        <text class="field-label">区域大小</text>
        <view class="tabs">
          <button
            v-for="option in sizeOptions"
            :key="option.value"
            class="tab"
            :class="{ active: size === option.value }"
            @tap="size = option.value"
          >
            {{ option.label }}
          </button>
        </view>
      </template>
    </view>

    <view class="panel">
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

      <button class="primary-button" :disabled="submitting || !filePath" @tap="submit">
        {{ submitting ? "处理中，请稍候..." : "开始去水印" }}
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
        <text class="key">水印区域示意</text>
        <image class="preview-image" :src="toAbsoluteUrl(result.preview_url)" mode="widthFix" />
      </view>

      <view v-if="result.regions && result.regions.length" class="result-line">
        <text class="key">去除区域</text>
        <text class="value">{{ result.regions.length }} 处 · {{ regionSummary }}</text>
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

import { API_BASE_URL, pollTask, uploadVideoWatermark } from "../../services/api";
import type { TaskResponse, VideoWatermarkResult } from "../../types/task";

type Mode = "auto" | "manual";
type RegionKey = "bottom_right" | "bottom_left" | "top_right" | "top_left" | "bottom_center" | "top_center";
type Size = "small" | "medium" | "large";
type Method = "delogo" | "inpaint";

const modeOptions: Array<{ label: string; value: Mode }> = [
  { label: "智能检测", value: "auto" },
  { label: "手动指定", value: "manual" },
];

const regionOptions: Array<{ label: string; value: RegionKey }> = [
  { label: "右下角", value: "bottom_right" },
  { label: "左下角", value: "bottom_left" },
  { label: "右上角", value: "top_right" },
  { label: "左上角", value: "top_left" },
  { label: "底部中间", value: "bottom_center" },
  { label: "顶部中间", value: "top_center" },
];

const sizeOptions: Array<{ label: string; value: Size }> = [
  { label: "小", value: "small" },
  { label: "中", value: "medium" },
  { label: "大", value: "large" },
];

const methodOptions: Array<{ label: string; value: Method }> = [
  { label: "快速（推荐）", value: "delogo" },
  { label: "精细（较慢）", value: "inpaint" },
];

const mode = ref<Mode>("auto");
const region = ref<RegionKey>("bottom_right");
const size = ref<Size>("medium");
const method = ref<Method>("delogo");

const filePath = ref("");
const fileLabel = ref("");
const submitting = ref(false);
const task = ref<TaskResponse | null>(null);

const modeHint = computed(() =>
  mode.value === "auto"
    ? "自动识别画面四角固定不动的文字/角标水印，适合各类 AI 生成视频"
    : "自己指定水印位置，智能检测识别不准时使用"
);

const methodHint = computed(() =>
  method.value === "delogo"
    ? "用周围画面插值填补水印区域，速度快，适合多数场景"
    : "逐帧修复水印区域，背景复杂时效果更自然，耗时更久"
);

const result = computed(() => {
  if (task.value?.status !== "success") {
    return null;
  }
  return task.value.result_payload as VideoWatermarkResult;
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

const regionSummary = computed(() => {
  const regions = result.value?.regions ?? [];
  if (!regions.length) {
    return "-";
  }
  if (mode.value === "manual" || regions[0].source === "manual") {
    return "手动指定区域";
  }
  return `自动检测（置信度 ${(Math.max(...regions.map((item) => item.confidence)) * 100).toFixed(0)}%）`;
});

function chooseVideo() {
  uni.chooseMedia({
    count: 1,
    mediaType: ["video"],
    sourceType: ["album", "camera"],
    maxDuration: 60,
    success: (response) => {
      const file = response.tempFiles[0] as unknown as {
        tempFilePath: string;
        size?: number;
        duration?: number;
      };
      if (!file?.tempFilePath) {
        return;
      }
      filePath.value = file.tempFilePath;
      task.value = null;
      const parts = [formatSize(file.size)];
      if (file.duration) {
        parts.push(`${Math.round(file.duration)} 秒`);
      }
      fileLabel.value = parts.filter(Boolean).join(" · ");
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
  uni.showLoading({ title: "上传中...", mask: true });
  try {
    const created = await uploadVideoWatermark(filePath.value, {
      mode: mode.value,
      region: mode.value === "manual" ? region.value : "",
      size: size.value,
      method: method.value,
    });
    uni.hideLoading();
    task.value = created;
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

function toAbsoluteUrl(value: string): string {
  if (!value) {
    return "";
  }
  if (value.startsWith("http://") || value.startsWith("https://")) {
    return value;
  }
  return `${API_BASE_URL}${value}`;
}

function formatSize(size?: number): string {
  if (!size) {
    return "";
  }
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }
  return `${Math.max(1, Math.round(size / 1024))} KB`;
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
  background: linear-gradient(135deg, #2563eb, #38bdf8);
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

.field-label {
  margin-top: 8rpx;
  color: #475467;
  font-size: 26rpx;
  font-weight: 600;
}

.hint {
  color: #667085;
  font-size: 24rpx;
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
.region-chip::after,
.download-button::after {
  border: 0;
}

.tab.active {
  color: #fff;
  background: #2563eb;
}

.region-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14rpx;
}

.region-chip {
  padding: 0;
  border-radius: 14rpx;
  color: #475467;
  background: #f1f5f9;
  font-size: 25rpx;
}

.region-chip.active {
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

.primary-button[disabled] {
  color: #fff;
  background: #a7d9b9;
}

.preview-video {
  width: 100%;
  height: 420rpx;
  border-radius: 16rpx;
  background: #000;
}

.preview-image {
  width: 100%;
  border-radius: 16rpx;
}

.file-label {
  color: #667085;
  font-size: 24rpx;
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
  color: #2563eb;
  background: #eff6ff;
  font-size: 25rpx;
}

.error {
  color: #dc2626;
  font-size: 26rpx;
}
</style>
