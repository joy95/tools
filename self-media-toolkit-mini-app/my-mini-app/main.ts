import { createSSRApp } from 'vue'
import App from './App.vue'
import uviewPlus from 'uview-plus'; // 引入 uView Plus UI 组件库
import './uni.scss'; // 引入 uni-scss 基础样式，如果你的项目有的话

export function createApp() {
  const app = createSSRApp(App)
  app.use(uviewPlus) // 注册 uView Plus
  return {
    app
  }
}
