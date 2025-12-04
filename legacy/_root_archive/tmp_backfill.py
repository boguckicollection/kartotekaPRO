import os, sqlite3
base = os.environ.get("SHOPER_IMAGE_BASE") or "https://sklep839679.shoparena.pl/upload/images/"
base = base.rstrip('/') + '/'
con = sqlite3.connect('storage/app.db')
cur = con.cursor()
cur.execute('select count(*) from products where image is not null')
before = cur.fetchone()[0]
cur.execute('''
UPDATE products
SET image = CASE
  WHEN main_image_unic_name IS NOT NULL AND main_image_extension IS NOT NULL
    THEN ? || main_image_unic_name || '.' || main_image_extension
  WHEN main_image_gfx_id IS NOT NULL AND main_image_extension IS NOT NULL
    THEN ? || main_image_gfx_id || '.' || main_image_extension
  ELSE image
END
WHERE image IS NULL AND (
  (main_image_unic_name IS NOT NULL AND main_image_extension IS NOT NULL)
  OR (main_image_gfx_id IS NOT NULL AND main_image_extension IS NOT NULL)
)
''', (base, base))
con.commit()
cur.execute('select changes()')
updated = cur.fetchone()[0]
cur.execute('select count(*) from products where image is not null')
after = cur.fetchone()[0]
con.close()
print({'updated': updated, 'with_image_before': before, 'with_image_after': after, 'base': base})
