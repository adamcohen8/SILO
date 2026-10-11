"""Portable volume-contract fixtures; no actual Windows/disk acceptance."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.managed_code_storage import ManagedVolume,volume_record

RECORD={'format':1,'epoch':'a'*32,'drive':'Q',
    'volume_name':r'\\?\Volume{12345678-1234-1234-1234-123456789abc}'+'\\',
    'volume_serial':123,'pool_index':2,'maximum_bytes':16*1024*1024,'user_sid':'S-1-5-21-1-2-3-1001'}


class NativeFixture:
    def __init__(self):
        self.kernel=Mock();self.nodes={1:dict(directory=True,children={'pool':2},parent=None,name=''),
            2:dict(directory=True,children={},parent=1,name='pool')}
        self.handles={};self.next_handle=100;self.next_node=3;self.disposed=set()
        self.kernel.GetVolumeNameForVolumeMountPointW.side_effect=self.volume_name
        self.kernel.GetDiskFreeSpaceExW.side_effect=self.space
        self.kernel.GetVolumeInformationW.side_effect=self.filesystem
        self.actual_name=RECORD['volume_name'];self.total=RECORD['maximum_bytes']
    def volume_name(self,drive,out,size):out.value=self.actual_name;return 1
    def space(self,path,available,total,free):
        total._obj.value=self.total;available._obj.value=self.total;free._obj.value=self.total;return 1
    def filesystem(self,*args):args[-2].value='NTFS';return 1
    def handle(self,node):
        self.next_handle+=1;self.handles[self.next_handle]=node;return self.next_handle
    def open_drive(self,drive):return self.handle(1)
    def open_child(self,parent,name,*,directory=None,security=False,create=False,delete=False):
        node=self.handles[parent];children=self.nodes[node]['children']
        if create:
            if name in children:raise FileExistsError()
            child=self.next_node;self.next_node+=1
            self.nodes[child]=dict(directory=directory is True,children={},parent=node,name=name)
            children[name]=child
        else:child=children[name]
        return self.handle(child)
    def info(self,handle):
        node=self.handles[handle];value=self.nodes[node]
        return SimpleNamespace(directory=value['directory'],volume=123,index=node,
            disk=True,reparse=value.get('reparse',False),offline=False,links=1)
    def names(self,handle):return iter(['.','..',*self.nodes[self.handles[handle]]['children']])
    def write(self,handle,data):self.nodes[self.handles[handle]]['data']=data
    def discard(self,handle):
        node=self.handles[handle]
        if self.nodes[node]['children']:raise OSError('Synthetic nonempty directory')
        self.disposed.add(node)
    def close(self,handle):
        node=self.handles.pop(handle)
        if node in self.disposed:
            value=self.nodes.pop(node);self.nodes[value['parent']]['children'].pop(value['name'])
            self.disposed.remove(node)


class ManagedVolumeTests(unittest.TestCase):
    def setUp(self):
        self.native=NativeFixture();self.record=copy.deepcopy(RECORD)
        self.security=SimpleNamespace(check=Mock(),store=SimpleNamespace(get=lambda name:self.record))
        self.patches=[patch('local_ai_appliance.managed_code_storage.os',SimpleNamespace(name='nt')),
            patch('local_ai_appliance.managed_code_storage.current_user_sid',return_value=RECORD['user_sid']),
            patch('local_ai_appliance.windows_native.NativeFiles',return_value=self.native),
            patch('local_ai_appliance.machine_security.protected_acl')]
        for item in self.patches:item.start();self.addCleanup(item.stop)
    def volume(self):return ManagedVolume(self.security,16*1024*1024)
    def test_exact_volume_claim_is_exclusive_and_cleanup_retires_only_owned_work(self):
        volume=self.volume()
        with self.assertRaises(AccessDenied):self.volume()
        pool=volume.handles[-1]
        work=self.native.open_child(pool,'work',directory=True,create=True)
        file=self.native.open_child(work,'synthetic.txt',directory=False,create=True)
        self.native.close(file);self.native.close(work)
        volume.close()
        self.assertEqual(self.native.nodes[2]['children'],{})
        self.assertEqual(self.native.handles,{})
        self.volume().close()
    def test_crash_marker_or_unexpected_files_block_reuse_without_deletion(self):
        volume=self.volume()
        # Simulate host death: handles close, durable unretired lease remains.
        self.native.close(volume.lease)
        for handle in reversed(volume.handles):self.native.close(handle)
        with self.assertRaises(AccessDenied):self.volume()
        self.assertEqual(set(self.native.nodes[2]['children']),{'lease.json'})
    def test_unsafe_cleanup_retains_lease_and_never_follows_reparse_object(self):
        volume=self.volume();work=self.native.open_child(volume.handles[-1],'work',directory=True,create=True)
        self.native.nodes[self.native.handles[work]]['reparse']=True;self.native.close(work)
        with self.assertRaises(AccessDenied):volume.close()
        self.assertEqual(set(self.native.nodes[2]['children']),{'work','lease.json'})
        self.assertEqual(self.native.handles,{})
    def test_mapping_capacity_identity_and_account_drift_prevent_claim(self):
        for field,value in [('user_sid','S-1-5-21-9-9-9-1001'),('pool_index',99),('volume_serial',456),
                            ('volume_name',r'\\?\Volume{99999999-1234-1234-1234-123456789abc}'+'\\')]:
            with self.subTest(field=field):
                self.record=copy.deepcopy(RECORD);self.record[field]=value
                with self.assertRaises(AccessDenied):self.volume()
                self.assertEqual(self.native.nodes[2]['children'],{})
        self.record=copy.deepcopy(RECORD);self.native.total=32*1024*1024
        with self.assertRaises(AccessDenied):self.volume()
    def test_record_rejects_physical_disk_paths_unknown_fields_and_unbounded_budget(self):
        self.assertEqual(volume_record(RECORD),RECORD)
        for field,value in [('drive','C'),('volume_name',r'\\.\PhysicalDrive0'),
                            ('maximum_bytes',128*1024*1024),('format',True),('user_sid','Everyone')]:
            bad=copy.deepcopy(RECORD);bad[field]=value
            with self.assertRaises(AccessDenied):volume_record(bad)
        with self.assertRaises(AccessDenied):volume_record(RECORD|{'force':True})
