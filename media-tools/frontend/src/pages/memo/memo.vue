<template>
  <view class="page">
    <view v-if="memos.length === 0" class="empty">
      <text class="empty-icon">记</text>
      <text class="empty-title">暂无备忘录</text>
      <text class="empty-desc">点击右下角按钮添加快捷提示词</text>
    </view>

    <view v-for="memo in memos" :key="memo.id" class="memo-card">
      <text class="memo-time">{{ memo.createdAt }}</text>
      <text class="memo-content">{{ memo.content }}</text>
      <view class="memo-actions">
        <button class="copy-button" @tap="copy(memo.content)">复制文案</button>
        <button class="delete-button" @tap="removeMemo(memo.id)">删除</button>
      </view>
    </view>

    <button class="fab" @tap="openForm">+</button>

    <view v-if="showForm" class="modal-mask" @tap="closeForm">
      <view class="modal-panel" @tap.stop>
        <text class="modal-title">添加备忘录</text>
        <textarea v-model="content" class="textarea" placeholder="记录常用提示词或文案" />
        <view class="modal-actions">
          <button class="ghost-button" @tap="closeForm">取消</button>
          <button class="primary-button" :disabled="!content.trim()" @tap="addMemo">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app";
import { ref } from "vue";

interface MemoRecord {
  id: string;
  content: string;
  createdAt: string;
}

const STORAGE_KEY = "media-tools:memos";

const content = ref("");
const memos = ref<MemoRecord[]>([]);
const showForm = ref(false);

onShow(() => {
  loadMemos();
});

function addMemo() {
  const text = content.value.trim();
  if (!text) {
    return;
  }

  memos.value = [
    {
      id: `${Date.now()}`,
      content: text,
      createdAt: formatNow(),
    },
    ...memos.value,
  ];
  content.value = "";
  showForm.value = false;
  saveMemos();
  uni.showToast({ title: "已添加", icon: "success" });
}

function openForm() {
  showForm.value = true;
}

function closeForm() {
  content.value = "";
  showForm.value = false;
}

function copy(text: string) {
  uni.setClipboardData({
    data: text,
    success: () => uni.showToast({ title: "已复制", icon: "success" }),
  });
}

function removeMemo(id: string) {
  memos.value = memos.value.filter((memo) => memo.id !== id);
  saveMemos();
  uni.showToast({ title: "已删除", icon: "success" });
}

function loadMemos() {
  const value = uni.getStorageSync(STORAGE_KEY);
  memos.value = Array.isArray(value) ? value.filter(isMemoRecord) : [];
}

function saveMemos() {
  uni.setStorageSync(STORAGE_KEY, memos.value);
}

function isMemoRecord(value: unknown): value is MemoRecord {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Record<string, unknown>;
  return typeof record.id === "string" && typeof record.content === "string" && typeof record.createdAt === "string";
}

function formatNow(): string {
  const date = new Date();
  const pad = (value: number) => `${value}`.padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  box-sizing: border-box;
  padding: 28rpx 28rpx 140rpx;
}

.memo-card {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  margin-bottom: 24rpx;
  padding: 28rpx;
  border-radius: 24rpx;
  background: #fff;
}

.modal-title {
  color: #172033;
  font-size: 32rpx;
  font-weight: 700;
}

.textarea {
  width: 100%;
  min-height: 220rpx;
  box-sizing: border-box;
  padding: 20rpx;
  border-radius: 18rpx;
  background: #f8fafc;
  font-size: 28rpx;
  line-height: 1.6;
}

.primary-button {
  flex: 1;
  border-radius: 999rpx;
  color: #fff;
  background: #2563eb;
}

.primary-button::after,
.ghost-button::after,
.fab::after,
.delete-button::after,
.copy-button::after {
  border: 0;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  min-height: 520rpx;
  text-align: center;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
  color: #2563eb;
  background: #eff6ff;
  font-size: 40rpx;
  font-weight: 700;
}

.empty-title {
  color: #172033;
  font-size: 32rpx;
  font-weight: 700;
}

.empty-desc {
  color: #667085;
  font-size: 26rpx;
}

.memo-time {
  color: #667085;
  font-size: 24rpx;
}

.memo-content {
  color: #172033;
  font-size: 28rpx;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.memo-actions {
  display: flex;
  gap: 16rpx;
}

.copy-button {
  padding: 0 24rpx;
  border-radius: 999rpx;
  color: #2563eb;
  background: #eff6ff;
  font-size: 24rpx;
}

.delete-button {
  padding: 0 24rpx;
  border-radius: 999rpx;
  color: #dc2626;
  background: #fef2f2;
  font-size: 24rpx;
}

.fab {
  position: fixed;
  right: 40rpx;
  bottom: 56rpx;
  z-index: 10;
  width: 104rpx;
  height: 104rpx;
  padding: 0;
  border-radius: 50%;
  color: #fff;
  background: #2563eb;
  font-size: 52rpx;
  line-height: 104rpx;
  box-shadow: 0 16rpx 36rpx rgba(37, 99, 235, 0.28);
}

.modal-mask {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 20;
  display: flex;
  align-items: flex-end;
  padding: 28rpx;
  background: rgba(15, 23, 42, 0.45);
}

.modal-panel {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
  width: 100%;
  box-sizing: border-box;
  padding: 32rpx;
  border-radius: 28rpx;
  background: #fff;
}

.modal-actions {
  display: flex;
  gap: 20rpx;
}

.ghost-button {
  flex: 1;
  border-radius: 999rpx;
  color: #475467;
  background: #f1f5f9;
}
</style>
