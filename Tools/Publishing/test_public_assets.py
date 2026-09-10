"""Tests for export boundaries, frozen input identity and tamper detection."""
import hashlib,json,os
from pathlib import Path
import subprocess,tempfile,unittest
import public_assets as p

class PublicAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'source').mkdir()
        self.file=self.root/'source'/'value.txt';self.file.write_text('public text',encoding='utf-8')
        self.item={'source':'source/value.txt','path':'data/value.txt','sha256':p.digest(self.file),'bytes':self.file.stat().st_size}
        self.plan=self.root/'plan.json';self.write_plan([self.item]);self.out=self.root/'output'
    def write_plan(self,items):
        self.plan.write_text(json.dumps({'schema':p.SCHEMA,'files':items}),encoding='utf-8')
    def export(self):return p.export(self.root,self.plan,self.out)
    def test_valid_then_content_tamper(self):
        self.assertEqual(self.export()['status'],'pass')
        (self.out/'data/value.txt').write_text('changed',encoding='utf-8')
        with self.assertRaises(ValueError):p.verify(self.out)
    def test_changed_frozen_source_writes_nothing(self):
        self.file.write_text('changed',encoding='utf-8')
        with self.assertRaises(ValueError):self.export()
        self.assertFalse(self.out.exists())
    def test_existing_output_is_not_overwritten(self):
        self.out.mkdir();(self.out/'keep').write_text('user')
        with self.assertRaises(ValueError):self.export()
        self.assertEqual((self.out/'keep').read_text(),'user')
    def test_path_escape_and_windows_drive_rejected(self):
        for field in ('source','path'):
            for name in ('../outside','/absolute','C:/outside','folder\\name'):
                with self.subTest(field=field,name=name):
                    item=dict(self.item);item[field]=name;self.write_plan([item])
                    with self.assertRaises(ValueError):self.export()
                    self.assertFalse(self.out.exists())
    def test_case_collision_rejected_before_writing(self):
        duplicate=dict(self.item);duplicate['path']='DATA/VALUE.TXT';self.write_plan([self.item,duplicate])
        with self.assertRaises(ValueError):self.export()
        self.assertFalse(self.out.exists())
    def test_metadata_privacy_rejected_before_writing(self):
        data=p.read_json(self.plan);data['note']='C:/Users/Private/file';self.plan.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.export()
        self.assertFalse(self.out.exists())
    def test_external_manifest_hash_required_to_match(self):
        result=self.export()
        with self.assertRaises(ValueError):p.verify(self.out,'0'*64)
        self.assertEqual(p.verify(self.out,result['manifestSha256'])['externalManifestHash'],'matched')
    def test_extra_file_is_not_ignored(self):
        self.export();(self.out/'extra.txt').write_text('unreviewed')
        with self.assertRaises(ValueError):p.verify(self.out)
    def test_private_path_rejected_but_https_allowed(self):
        self.file.write_text('https://github.com/example/repository',encoding='utf-8');p.inspect_text(self.file)
        self.file.write_text('C:/Users/Private/file.txt',encoding='utf-8')
        with self.assertRaises(ValueError):p.inspect_text(self.file)
    def test_directory_link_is_rejected(self):
        real=self.root/'real';real.mkdir();link=self.root/'link'
        if os.name=='nt':
            command=['powershell','-NoProfile','-Command',"New-Item -ItemType Junction -Path '"+str(link)+"' -Target '"+str(real)+"' | Out-Null"]
            result=subprocess.run(command,capture_output=True)
            if result.returncode:self.skipTest('junction creation unavailable')
        else:link.symlink_to(real,target_is_directory=True)
        try:
            with self.assertRaises(ValueError):p.safe_join(self.root,'link/missing.txt')
        finally:
            if os.name=='nt':os.rmdir(link)
            else:link.unlink()

if __name__=='__main__':unittest.main()
