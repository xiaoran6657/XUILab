import unittest
from unittest.mock import Mock,patch
from adaptive_focus import StartupFocus
from startup_focus import WindowsFocus

class FocusAttachment(unittest.TestCase):
    def make(self):
        obj=object.__new__(StartupFocus);obj.api=Mock();obj.kernel=Mock()
        obj.kernel.GetCurrentThreadId.return_value=10
        obj.api.GetWindowThreadProcessId.return_value=20
        obj.api.AttachThreadInput.return_value=True
        obj.owner=Mock(return_value=42)
        return obj
    def test_detaches_after_success(self):
        obj=self.make()
        with patch.object(WindowsFocus,"activate",return_value=False):self.assertTrue(obj.activate(100,42))
        self.assertEqual(obj.api.AttachThreadInput.call_args_list[0].args,(10,20,True))
        self.assertEqual(obj.api.AttachThreadInput.call_args_list[-1].args,(10,20,False))
    def test_detaches_after_exception(self):
        obj=self.make();obj.api.ShowWindow.side_effect=RuntimeError("failure")
        with patch.object(WindowsFocus,"activate",return_value=False),self.assertRaises(RuntimeError):obj.activate(100,42)
        self.assertEqual(obj.api.AttachThreadInput.call_args_list[-1].args,(10,20,False))
    def test_owner_change_prevents_mutation(self):
        obj=self.make();obj.owner.return_value=99
        with self.assertRaises(ValueError):obj.activate(100,42)
        obj.api.AttachThreadInput.assert_not_called();obj.api.ShowWindow.assert_not_called()

if __name__=="__main__":unittest.main()
