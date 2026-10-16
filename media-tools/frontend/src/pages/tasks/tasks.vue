<template>
  <view class="page">
    <button class="refresh-button" :disabled="loading" @tap="loadTasks">
      {{ loading ? "加载中..." : "刷新任务" }}
    </button>

    <view v-if="tasks.length === 0 && !loading" class="empty">暂无任务</view>

    <view v-for="task in tasks" :key="task.id" class="task-card">
      <view class="card-head">
        <text class="task-type">{{ typeLabel(task.type) }}</text>
        <text class="badge" :class="task.status">{{ task.status }} · {{ task.progress }}%</text>
      </view>
      <text class="task-id">ID：{{ task.id }}</text>
      <progress :percent="task.progress" stroke-width="6" active />
      <text v-if="task.error_message" class="error">{{ task.error_message }}</text>
      <view v-if="Object.keys(task.result_payload).length > 0" class="json-box">
        <text>{{ formatJson(task.result_payload) }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app";
import { ref } from "vue";

import { listTasks } from "../../services/api";
import type { TaskResponse, TaskType } from "../../types/task";

const tasks = ref<TaskResponse[]>([]);
const loading = ref(false);

onShow(() => {
  void loadTasks();
});

async function loadTasks() {
  loading.value = true;
  try {
    tasks.value = await listTasks();
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "任务加载失败",
      icon: "none",
    });
  } finally {
    loading.value = false;
  }
}

function typeLabel(type: TaskType): string {
  const labels: Record<TaskType, string> = {
    link_parse: "链接解析",
    remove_watermark: "去水印",
    video_watermark: "视频去水印",
    remove_subtitle: "去字幕",
    ocr_extract: "OCR",
    video_generate: "图文生成视频",
  };
  return labels[type];
}

function formatJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}
</script>

<style scoped>
.page {
  padding: 28rpx;
}

.refresh-button {
  margin-bottom: 24rpx;
  border-radius: 999rpx;
  color: #fff;
  background: #2563eb;
}

.refresh-button::after {
  border: 0;
}

.empty {
  padding: 60rpx 0;
  text-align: center;
  color: #667085;
  font-size: 28rpx;
}

.task-card {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
  margin-bottom: 24rpx;
  padding: 28rpx;
  border-radius: 24rpx;
  background: #fff;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}

.task-type {
  color: #172033;
  font-size: 30rpx;
  font-weight: 700;
}

.task-id {
  color: #667085;
  font-size: 24rpx;
  word-break: break-all;
}

.badge {
  flex: none;
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  color: #2563eb;
  background: #eff6ff;
  font-size: 24rpx;
}

.badge.success {
  color: #16a34a;
  background: #f0fdf4;
}

.badge.failed {
  color: #dc2626;
  background: #fef2f2;
}

.json-box {
  padding: 20rpx;
  border-radius: 16rpx;
  background: #f8fafc;
  color: #334155;
  font-size: 24rpx;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.error {
  color: #dc2626;
  font-size: 26rpx;
}
</style>
