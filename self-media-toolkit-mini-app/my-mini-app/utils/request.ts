import { Utoast } from 'uview-plus'; // 导入 UToast

const BASE_URL = 'http://your-backend-api.com'; // 后端API的基础URL

interface RequestOptions extends UniApp.RequestOptions {
  showLoading?: boolean; // 是否显示loading
  showErrorToast?: boolean; // 是否显示错误提示
}

interface UploadFileOptions extends UniApp.UploadFileOption {
  showLoading?: boolean; // 是否显示loading
  showErrorToast?: boolean; // 是否显示错误提示
}

// 通用请求封装
export const request = <T = any>(options: RequestOptions): Promise<T> => {
  const { url, method = 'GET', data, showLoading = true, showErrorToast = true } = options;

  return new Promise((resolve, reject) => {
    if (showLoading) {
      uni.showLoading({
        title: '加载中...',
        mask: true,
      });
    }

    uni.request({
      url: BASE_URL + url,
      method,
      data,
      header: {
        // TODO: 添加认证Token
        // 'Authorization': 'Bearer ' + uni.getStorageSync('token'),
        'Content-Type': 'application/json',
      },
      success: (res) => {
        if (res.statusCode === 200) {
          resolve(res.data as T);
        } else {
          if (showErrorToast) {
            Utoast.show({
              type: 'error',
              message: (res.data as any)?.message || '请求失败',
            });
          }
          reject(res);
        }
      },
      fail: (err) => {
        if (showErrorToast) {
          Utoast.show({
            type: 'error',
            message: '网络请求失败',
          });
        }
        reject(err);
      },
      complete: () => {
        if (showLoading) {
          uni.hideLoading();
        }
      },
    });
  });
};

// 通用文件上传封装
export const uploadFile = <T = any>(options: UploadFileOptions): Promise<T> => {
  const { url, filePath, name, formData, showLoading = true, showErrorToast = true } = options;

  return new Promise((resolve, reject) => {
    if (showLoading) {
      uni.showLoading({
        title: '上传中...',
        mask: true,
      });
    }

    uni.uploadFile({
      url: BASE_URL + url,
      filePath,
      name,
      formData,
      header: {
        // TODO: 添加认证Token
        // 'Authorization': 'Bearer ' + uni.getStorageSync('token'),
      },
      success: (res) => {
        if (res.statusCode === 200) {
          try {
            resolve(JSON.parse(res.data) as T);
          } catch (e) {
            // 如果后端返回的不是JSON，直接返回原始数据
            resolve(res.data as T);
          }
        } else {
          if (showErrorToast) {
            Utoast.show({
              type: 'error',
              message: JSON.parse(res.data as string)?.message || '上传失败',
            });
          }
          reject(res);
        }
      },
      fail: (err) => {
        if (showErrorToast) {
          Utoast.show({
            type: 'error',
            message: '网络上传失败',
          });
        }
        reject(err);
      },
      complete: () => {
        if (showLoading) {
          uni.hideLoading();
        }
      },
    });
  });
};

// 通用文件下载封装
export const downloadFile = (url: string, fileName?: string): Promise<string> => {
  return new Promise((resolve, reject) => {
    uni.showLoading({
      title: '下载中...',
      mask: true,
    });
    uni.downloadFile({
      url: BASE_URL + url, // 同样使用BASE_URL
      filePath: fileName ? `${uni.env.USER_DATA_PATH}/${fileName}` : undefined, // 尝试指定文件名
      success: (res) => {
        if (res.statusCode === 200) {
          resolve(res.tempFilePath);
        } else {
          Utoast.show({
            type: 'error',
            message: '下载失败',
          });
          reject(res);
        }
      },
      fail: (err) => {
        Utoast.show({
          type: 'error',
          message: '网络下载失败',
        });
        reject(err);
      },
      complete: () => {
        uni.hideLoading();
      },
    });
  });
};
