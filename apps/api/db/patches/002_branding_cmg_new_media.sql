-- 已有库：将演示组织名称与 Logo 更新为总台研究院新媒体研究部（Logo 由前端 public/cmg-new-media-brand.png 提供）
UPDATE organizations AS o
SET
  name = '中央广播电视总台研究院新媒体研究部',
  logo_url = '/cmg-new-media-brand.png'
FROM users AS u
WHERE u.organization_id = o.id AND u.email = 'owner@demo.com';
