# 前端测试指导文档 (uni-app 微信小程序)

## 1. 概述
本文档旨在指导前端开发者对自媒体工具箱 uni-app 微信小程序进行有效的测试，确保项目质量和用户体验。测试将涵盖单元测试、集成测试和真机调试。

## 2. 单元测试 (使用 Jest)

### 2.1 目的
对独立函数、工具类和 Vue 组件的逻辑进行验证，确保其在隔离环境下的正确性。

### 2.2 配置 Jest
uni-app 项目通常需要对 Jest 进行一些额外配置，以正确处理 Vue 单文件组件 (`.vue`) 和 uni-app 特定的 API。以下是一个基本的配置示例，具体可能需要根据你的项目结构进行微调。

1.  **安装 Jest 及相关依赖**:
    ```bash
    cd self-media-toolkit-mini-app/my-mini-app
    npm install --save-dev jest @vue/test-utils@next @vue/compiler-sfc babel-jest @babel/core @babel/preset-env vue-jest
    # 如果是 TypeScript 项目
    npm install --save-dev ts-jest @babel/preset-typescript @types/jest
    ```

2.  **配置 `babel.config.js`** (如果项目有的话，确保包含必要的 preset):
    ```javascript
    module.exports = {
      presets: [
        ['@babel/preset-env', { targets: { node: 'current' } }],
        // 如果是 TypeScript 项目
        '@babel/preset-typescript',
      ],
    };
    ```

3.  **创建 `jest.config.js`** (在项目根目录):
    ```javascript
    module.exports = {
      preset: 'ts-jest', // 如果是 TypeScript 项目
      testEnvironment: 'jsdom',
      moduleFileExtensions: [
        'js',
        'ts',
        'json',
        'vue',
      ],
      transform: {
        '^.+\.vue$': 'vue-jest',
        '^.+\.ts$': 'ts-jest',
        '^.+\.js$': 'babel-jest',
      },
      moduleNameMapper: {
        '^@/(.*)$': '<rootDir>/src/$1',
        // uni-app 的 @dcloudio/uni-app 等模块需要 mock
        '^@dcloudio/uni-app$': '<rootDir>/test/mock/uni-app.js',
        '^@dcloudio/uni-uts$': '<rootDir>/test/mock/uni-uts.js',
        // ... 其他 uni-app 模块的 mock
      },
      testMatch: [
        '<rootDir>/__tests__/**/*.spec.ts',
        '<rootDir>/**/*.spec.ts',
        '<rootDir>/**/*.test.ts',
      ],
      collectCoverage: true,
      collectCoverageFrom: [
        '<rootDir>/src/**/*.{ts,vue}',
        '!**/node_modules/**',
      ],
      setupFiles: ['<rootDir>/test/setup.ts'], // 可以在这里引入全局 mock 或 setup 文件
    };
    ```

4.  **创建 `test/mock/uni-app.js` (或 `ts`)**:
    由于 Jest 运行在 Node.js 环境，uni-app 的 `uni.*` API 需要被 Mock。这是一个简单的示例：
    ```javascript
    // test/mock/uni-app.js
    module.exports = {
      uni: {
        navigateTo: jest.fn(),
        showLoading: jest.fn(),
        hideLoading: jest.fn(),
        request: jest.fn(() => Promise.resolve({ statusCode: 200, data: {} })),
        uploadFile: jest.fn(() => Promise.resolve({ statusCode: 200, data: JSON.stringify({}) })),
        downloadFile: jest.fn(() => Promise.resolve({ statusCode: 200, tempFilePath: 'mock-path' })),
        setClipboardData: jest.fn(() => Promise.resolve()),
        showToast: jest.fn(),
        saveImageToPhotosAlbum: jest.fn(() => Promise.resolve()),
        saveVideoToPhotosAlbum: jest.fn(() => Promise.resolve()),
        share: jest.fn(() => Promise.resolve()),
        env: { USER_DATA_PATH: 'mock-user-data-path' },
      },
      onLoad: jest.fn((cb) => cb({ type: 'link' })), // mock onLoad for component testing
    };
    ```

5.  **创建测试文件**：在 `__tests__` 目录或组件同级目录下创建 `.spec.ts` 文件。
    例如，对 `utils/request.ts` 的测试：
    ```typescript
    // self-media-toolkit-mini-app/my-mini-app/utils/__tests__/request.spec.ts
    import { request, uploadFile, downloadFile } from '../request';

    describe('request utils', () => {
      beforeEach(() => {
        // 在每个测试前重置 mock
        uni.request.mockClear();
        uni.uploadFile.mockClear();
        uni.downloadFile.mockClear();
        uni.showLoading.mockClear();
        uni.hideLoading.mockClear();
      });

      test('request should call uni.request and resolve on success', async () => {
        uni.request.mockImplementationOnce(() => Promise.resolve({ statusCode: 200, data: { message: 'success' } }));
        const res = await request({ url: '/test' });
        expect(uni.request).toHaveBeenCalledTimes(1);
        expect(res).toEqual({ message: 'success' });
      });

      test('uploadFile should call uni.uploadFile and resolve on success', async () => {
        uni.uploadFile.mockImplementationOnce(() => Promise.resolve({ statusCode: 200, data: JSON.stringify({ url: 'test-url' }) }));
        const res = await uploadFile({ url: '/upload', filePath: 'temp-path', name: 'file' });
        expect(uni.uploadFile).toHaveBeenCalledTimes(1);
        expect(res).toEqual({ url: 'test-url' });
      });

      // ... 更多测试用例
    });
    ```

### 2.3 运行测试
在 `package.json` 的 `scripts` 中添加：
```json
{
  "scripts": {
    "test:unit": "jest"
  }
}
```
然后运行：
```bash
npm run test:unit
```

## 3. 集成测试

### 3.1 目的
验证多个模块协同工作时的正确性，模拟用户在不同页面间的操作流程，确保功能链条的完整性。

### 3.2 策略
*   **页面跳转测试**: 验证首页功能入口是否能正确跳转到对应的功能页面。
*   **数据流测试**: 模拟用户输入（链接或文件上传），检查数据是否正确传递到后端，并验证后端返回结果的正确性。
*   **交互逻辑测试**: 测试页面上的按钮点击、表单提交等交互是否符合预期。
*   **使用工具**: 可以考虑使用 `uni-app` 提供的 E2E 测试方案（如基于 Puppeteer 或 Cypress），但这通常在项目后期或对自动化要求较高时引入。
*   **手动测试**: 初期阶段，集成测试主要通过手动模拟用户操作进行。

### 3.3 关键测试点
*   **去水印功能**: 分别测试链接解析和文件上传两种方式，验证去水印结果的展示、下载和分享功能。
*   **文案提取功能**: 分别测试链接解析和文件上传两种方式，验证文案提取的准确性、复制功能。
*   **图文生成视频功能**: 验证图片上传、文案输入、视频生成任务提交、任务状态查询和视频结果的展示、下载、分享功能。

## 4. 真机调试

### 4.1 目的
在真实设备上运行小程序，验证界面适配、性能、API 调用、兼容性等问题。

### 4.2 步骤
1.  **在 HBuilderX 中运行**: 打开 `HBuilderX`，导入 `self-media-toolkit-mini-app/my-mini-app` 项目。
2.  **运行到微信开发者工具**: 在 `HBuilderX` 中点击“运行 -> 运行到小程序模拟器 -> 微信开发者工具”。
    *   确保已安装微信开发者工具并登录。
    *   在开发者工具中进行预览和调试。
3.  **真机预览/调试**: 在微信开发者工具中生成预览码，使用手机微信扫码进行真机预览。或通过 USB 连接手机进行真机调试。

### 4.3 关注点
*   **UI 适配**: 不同机型、屏幕尺寸下的界面显示是否正常。
*   **性能**: 页面加载速度、动画流畅度、大文件上传/下载时的表现。
*   **API 调用**: 所有后端 API 调用是否正常，是否出现跨域、网络错误等。
*   **权限**: 文件保存到相册、分享等功能是否正常获取和使用权限。
*   **用户体验**: 整体操作流程是否顺畅，提示信息是否清晰。

---

**测试启动**:
请根据上述指导，开始进行前端测试。如果你在配置或执行测试时遇到任何问题，或需要我提供进一步的帮助，请告诉我。
