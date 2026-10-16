<template>
  <view class="page">
    <view class="hero">
      <text class="eyebrow">Media Tools</text>
      <text class="title">自媒体工具箱</text>
      <text class="subtitle">链接解析、视频去水印、视频去字幕、图文生成视频，一站式提交后端任务。</text>
    </view>

    <view class="grid">
      <button class="card info" @tap="go('/pages/link-parse/link-parse')">
        <text class="card-icon">链</text>
        <text class="card-title">链接解析</text>
      </button>
      <button class="card primary" @tap="go('/pages/video-watermark/video-watermark')">
        <text class="card-icon">水</text>
        <text class="card-title">视频去水印</text>
      </button>
      <button class="card teal" @tap="go('/pages/video-subtitle/video-subtitle')">
        <text class="card-icon">幕</text>
        <text class="card-title">视频去字幕</text>
      </button>
      <button class="card success" @tap="go('/pages/file-process/file-process')">
        <text class="card-icon">文</text>
        <text class="card-title">文件处理</text>
      </button>
      <button class="card warning" @tap="go('/pages/video-generate/video-generate')">
        <text class="card-icon">影</text>
        <text class="card-title">图文生成视频</text>
      </button>
      <button class="card note" @tap="go('/pages/memo/memo')">
        <text class="card-icon">记</text>
        <text class="card-title">备忘录</text>
      </button>
      <button class="card muted" @tap="go('/pages/tasks/tasks')">
        <text class="card-icon">单</text>
        <text class="card-title">任务列表</text>
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
function go(url: string) {
  uni.navigateTo({ url });
}
</script>

<style scoped>
.page {
  padding: 32rpx;
}

.hero {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  padding: 40rpx 32rpx;
  border-radius: 28rpx;
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #38bdf8);
}

.eyebrow {
  font-size: 24rpx;
  opacity: 0.8;
}

.title {
  font-size: 44rpx;
  font-weight: 700;
}

.subtitle {
  font-size: 28rpx;
  line-height: 1.6;
  opacity: 0.92;
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24rpx;
  margin-top: 32rpx;
}

.card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  width: 100%;
  min-height: 168rpx;
  padding: 0;
  margin: 0;
  border: 0;
  border-radius: 20rpx;
  line-height: 1.3;
  text-align: center;
  background: #fff;
  box-shadow: 0 10rpx 28rpx rgba(15, 23, 42, 0.06);
}

.card::after {
  border: 0;
}

.card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  font-size: 28rpx;
  font-weight: 700;
  color: #fff;
}

.card-title {
  font-size: 24rpx;
  font-weight: 700;
  color: #172033;
}

.primary {
  background: #eff6ff;
}

.primary .card-icon {
  background: #2563eb;
}

.teal {
  background: #ecfeff;
}

.teal .card-icon {
  background: #0ea5e9;
}

.info {
  background: #eef2ff;
}

.info .card-icon {
  background: #4f46e5;
}

.success {
  background: #ecfdf3;
}

.success .card-icon {
  background: #16a34a;
}

.warning {
  background: #fffbeb;
}

.warning .card-icon {
  background: #f59e0b;
}

.note {
  background: #f5f3ff;
}

.note .card-icon {
  background: #7c3aed;
}

.muted {
  background: #f8fafc;
}

.muted .card-icon {
  background: #64748b;
}
</style>
