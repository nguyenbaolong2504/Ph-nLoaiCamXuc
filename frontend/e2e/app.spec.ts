import {test,expect} from '@playwright/test';
import path from 'node:path';

test('registration, consent, real image analysis, history and camera stop',async({page},testInfo)=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  const nav=async(name:string)=>{if(testInfo.project.name==='mobile')await page.getByRole('button',{name:'Mở menu'}).click();await page.locator('nav').getByRole('button',{name,exact:true}).click()};
  await page.goto('/');await page.getByRole('button',{name:'Đăng ký ngay'}).click();
  await page.getByLabel('Họ và tên').fill('Kiểm thử trình duyệt');
  await page.getByLabel('Địa chỉ email').fill(`browser-${testInfo.project.name}-${Date.now()}@example.com`);
  await page.getByLabel('Mật khẩu',{exact:true}).fill('Browser-test-password-2026');
  await page.getByRole('button',{name:'Tạo tài khoản',exact:true}).click();
  await expect(page.getByRole('heading',{name:/Xin chào/})).toBeVisible();
  await expect(page.locator('body')).not.toHaveJSProperty('scrollWidth',0);
  await page.screenshot({path:`../../../work/dashboard-${testInfo.project.name}.png`,fullPage:true});
  await nav('Phân tích ảnh');await page.getByRole('checkbox',{name:'Đồng ý xử lý hình ảnh'}).check();
  await page.getByRole('checkbox',{name:'Lưu kết quả vào lịch sử'}).check();
  await page.locator('input[type=file]').setInputFiles(path.resolve('../tests/assets/astronaut.png'));
  await page.getByRole('button',{name:'Phân tích biểu cảm',exact:true}).click();
  await expect(page.getByRole('button',{name:'Mặt 1',exact:true})).toBeVisible();
  await expect(page.getByText('Điểm mô hình:',{exact:false})).toBeVisible();
  await page.screenshot({path:`../../../work/analysis-${testInfo.project.name}.png`,fullPage:true});
  await nav('Lịch sử phân tích');await page.getByRole('button',{name:'astronaut.png',exact:true}).click();
  await expect(page.getByRole('dialog')).toBeVisible();await expect(page.getByRole('link',{name:'Xuất CSV'})).toBeVisible();await page.getByRole('button',{name:'Đóng chi tiết'}).click();
  await nav('Webcam trực tiếp');await page.getByRole('button',{name:'Bật camera',exact:true}).click();
  await expect(page.getByText('XEM TRƯỚC',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Bắt đầu phân tích',exact:true}).click();
  await expect(page.getByText('ĐANG PHÂN TÍCH',{exact:true})).toBeVisible();
  await expect(page.locator('.result-meta')).toBeVisible();
  await page.getByRole('button',{name:'Dừng & đóng camera',exact:true}).click();
  await expect(page.getByText('CHƯA KẾT NỐI',{exact:true})).toBeVisible();
  await expect(page.locator('.result-meta')).not.toBeVisible();
  const width=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,view:innerWidth}));expect(width.doc).toBeLessThanOrEqual(width.view+1);
  expect(errors).toEqual([]);
  // Remove analysis records created by this test; leave no saved face results.
  await page.request.delete('/api/users/me/data');
});
