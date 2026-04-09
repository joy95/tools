# 自媒体工具箱小程序前端 (uni-app)

这是一个基于 `uni-app` (Vue 3 + Composition API) 开发的自媒体工具箱小程序前端项目，提供了去水印、文案提取和图文生成视频等核心功能。

## 技术栈

*   **框架**: `uni-app` (Vue 3)
*   **UI 组件库**: `uview-plus`
*   **状态管理**: `Pinia`
*   **网络请求**: 自定义封装的 `uni.request` 和 `uni.uploadFile`

## 项目结构

```
my-mini-app/
├── components/           # 自定义组件 (如果需要)
├── pages/                # 页面文件
│   ├── index/            # 首页/功能列表
│   ├── watermark/        # 去水印功能页
│   ├── text-extract/     # 文案提取功能页
│   └── video-generate/   # 图文生成视频功能页
├── static/               # 静态资源 (图片、图标等)
├── utils/                # 工具函数 (如 request.ts)
├── App.vue               # 应用根组件
├── main.ts               # Vue 3 应用入口文件
├── manifest.json         # uni-app 配置 (项目名称、权限等)
├── pages.json            # 页面路由和窗口样式配置
├── uni.scss              # 全局 scss 样式文件
├── vite.config.ts        # Vite 配置 (如果使用 Vue CLI 创建，则可能为 vue.config.js)
└── package.json          # 项目依赖和脚本
```

## 开发指南

### 1. 安装依赖

进入前端项目目录 `self-media-toolkit-mini-app/my-mini-app`，安装项目依赖：

```bash
cd self-media-toolkit-mini-app/my-mini-app
npm install
```

### 2. 启动开发服务器

将项目编译到微信小程序并启动开发服务器：

```bash
npm run dev:mp-weixin
```

### 3. 在微信开发者工具中预览

1.  打开**微信开发者工具**。
2.  选择**“导入项目”**。
3.  项目路径选择 `self-media-toolkit-mini-app/my-mini-app/dist/dev/mp-weixin`。
4.  点击“导入”即可在开发者工具中预览和调试小程序。

### 4. 配置后端 API 地址

打开 `self-media-toolkit-mini-app/my-mini-app/utils/request.ts` 文件，将 `BASE_URL` 变量更新为你的后端服务实际运行的地址。如果在本地运行 Docker Compose，通常是 `http://localhost:8000`。

```typescript
// self-media-toolkit-mini-app/my-mini-app/utils/request.ts
const BASE_URL = 'http://localhost:8000'; // 更新为你的后端服务地址
```

### 5. 前端测试

参考 `self-media-toolkit-mini-app/my-mini-app/docs/frontend-testing-guide.md` 文档进行前端测试。

## 6. 注意事项

*   **后端 API 占位符**: 当前前端代码中的 API 地址仍是占位符，请务必根据后端实际部署情况进行更新。
*   **链接解析**: 后端 `tasks.py` 中的链接解析功能为模拟实现，实际部署时需要投入大量精力进行开发和维护。
*   **去水印和视频生成逻辑**: 后端 `tasks.py` 中的去水印和视频生成逻辑为简化版本，需要根据实际需求进行完善。
