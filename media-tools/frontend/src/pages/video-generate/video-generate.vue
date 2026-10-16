<template>
  <view class="page">
    <view class="notice">
      <text>当前后端已支持视频生成任务提交，暂未提供图片资产上传接口。这里先用图片资产 ID 提交任务，方便预览完整任务链路。</text>
    </view>

    <view class="panel">
      <text class="label">图片资产 ID</text>
      <input v-model="assetIdsText" class="input" placeholder="多个 ID 用英文逗号分隔，留空使用 preview-image" />
      <text class="hint">示例：image-1,image-2</text>
    </view>

    <view class="panel">
      <text class="label">视频文案</text>
      <textarea v-model="text" class="textarea" placeholder="输入要生成视频的文案" />
      <text class="label">模板</text>
      <input v-model="templateId" class="input" placeholder="default" />
      <button class="primary-button" :disabled="submitting || !text.trim()" @tap="submit">
        {{ submitting ? "生成中..." : "提交生成任务" }}
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
      <text class="section-title">生成结果</text>
      <text class="message">{{ result.message || "任务完成" }}</text>
      <view class="result-line">
        <text class="key">模板</text>
        <text class="value">{{ result.template_id || "-" }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import { createVideoGenerateTask, pollTask } from "../../services/api";
import type { TaskResponse, VideoGenerateResult } from "../../types/task";

const assetIdsText = ref("");
const text = ref("");
const templateId = ref("default");
const submitting = ref(false);
const task = ref<TaskResponse | null>(null);

const result = computed(() => {
  if (task.value?.status !== "success") {
    return null;
  }
  return task.value.result_payload as VideoGenerateResult;
});

async function submit() {
  if (!text.value.trim()) {
    return;
  }

  submitting.value = true;
  task.value = null;
  try {
    const imageAssetIds = assetIdsText.value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const created = await createVideoGenerateTask({
      image_asset_ids: imageAssetIds.length > 0 ? imageAssetIds : ["preview-image"],
      text: text.value.trim(),
      template_id: templateId.value.trim() || "default",
    });
    task.value = created;
    task.value = await pollTask(created.id);
  } catch (error) {
    showError(error);
  } finally {
    submitting.value = false;
  }
}

function showError(error: unknown) {
  uni.showToast({
    title: error instanceof Error ? error.message : "生成失败",
    icon: "none",
  });
}
</script>

<style scoped>
.page {
  padding: 28rpx;
}

.notice {
  margin-bottom: 24rpx;
  padding: 24rpx;
  border-radius: 20rpx;
  color: #92400e;
  background: #fffbeb;
  font-size: 26rpx;
  line-height: 1.6;
}

.panel {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
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

.input,
.textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 20rpx;
  border-radius: 18rpx;
  background: #f8fafc;
  font-size: 28rpx;
}

.textarea {
  min-height: 180rpx;
}

.hint {
  color: #667085;
  font-size: 24rpx;
}

.primary-button {
  border-radius: 999rpx;
  color: #fff;
  background: #f59e0b;
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

.error {
  color: #dc2626;
  font-size: 26rpx;
}
</style>
