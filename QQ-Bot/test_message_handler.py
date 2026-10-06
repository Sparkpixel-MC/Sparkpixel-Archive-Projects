"""message_handler.py 单元测试"""
import unittest
from unittest.mock import patch, MagicMock
import asyncio
import sys

# 模拟依赖模块
mock_config = MagicMock()
mock_config.AUTHORIZED_GROUPS = ["123456"]
mock_config.ADMIN_GROUP_ID = "123456"
mock_config.FINANCE_BLOCKED_USERS = []
mock_config.BASE_URL = "http://test"
mock_config.BASE_TOKEN = "test"
mock_config.HEALTH_URL = "https://health.sparkpixel.top/"
sys.modules['config'] = mock_config

mock_database = MagicMock()
sys.modules['database'] = mock_database

mock_server_monitor = MagicMock()
sys.modules['server_monitor'] = mock_server_monitor

mock_message_sender = MagicMock()
sys.modules['message_sender'] = mock_message_sender

mock_image_generator = MagicMock()
sys.modules['image_generator'] = mock_image_generator

from message_handler import handle_private_message, handle_group_message


class TestHandlePrivateMessagePay(unittest.TestCase):
    """测试私聊 /pay 命令处理"""

    def setUp(self):
        self.send_func = MagicMock()

    def test_pay_no_args(self):
        """测试 /pay 无参数"""
        obj = {"user_id": "789", "raw_message": "/pay"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("参数错误", args[0])

    def test_pay_only_receiver(self):
        """测试 /pay 只有接收人"""
        obj = {"user_id": "789", "raw_message": "/pay Steve"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("参数错误", args[0])

    def test_pay_invalid_amount(self):
        """测试无效金额"""
        obj = {"user_id": "789", "raw_message": "/pay Steve abc"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("金额格式错误", args[0])

    def test_pay_zero_amount(self):
        """测试金额为 0"""
        obj = {"user_id": "789", "raw_message": "/pay Steve 0"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("金额必须大于0", args[0])

    def test_pay_negative_amount(self):
        """测试负数金额"""
        obj = {"user_id": "789", "raw_message": "/pay Steve -100"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("金额必须大于0", args[0])

    def test_pay_amount_too_large(self):
        """测试金额超过上限"""
        obj = {"user_id": "789", "raw_message": "/pay Steve 1000001"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("不能超过100万", args[0])

    @patch("get_qqid.get_gamenick")
    def test_pay_sender_not_bound(self, mock_get_gamenick):
        """测试转账人未绑定"""
        mock_get_gamenick.return_value = None
        obj = {"user_id": "789", "raw_message": "/pay Steve 100"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("未找到您的游戏昵称", args[0])

    @patch("pay.check_player_exists")
    @patch("get_qqid.get_gamenick")
    def test_pay_receiver_not_exists(self, mock_get_gamenick, mock_check):
        """测试收款人不存在"""
        mock_get_gamenick.return_value = "Sender"
        mock_check.return_value = False
        obj = {"user_id": "789", "raw_message": "/pay NotExist 100"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("未找到玩家", args[0])

    @patch("pay.check_player_exists")
    @patch("get_qqid.get_gamenick")
    def test_pay_same_player(self, mock_get_gamenick, mock_check):
        """测试给自己转账"""
        mock_get_gamenick.return_value = "Steve"
        mock_check.return_value = True
        obj = {"user_id": "789", "raw_message": "/pay Steve 100"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("不能给自己转账", args[0])

    @patch("pay.transfer_money")
    @patch("pay.check_player_exists")
    @patch("get_qqid.get_gamenick")
    def test_pay_success(self, mock_get_gamenick, mock_check, mock_transfer):
        """测试转账成功"""
        mock_get_gamenick.return_value = "Sender"
        mock_check.return_value = True
        mock_transfer.return_value = {"success": True, "message": "转账成功", "response": "OK"}
        obj = {"user_id": "789", "raw_message": "/pay Receiver 100"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("转账成功", args[0])

    @patch("pay.transfer_money")
    @patch("pay.check_player_exists")
    @patch("get_qqid.get_gamenick")
    def test_pay_failure(self, mock_get_gamenick, mock_check, mock_transfer):
        """测试转账失败"""
        mock_get_gamenick.return_value = "Sender"
        mock_check.return_value = True
        mock_transfer.return_value = {"success": False, "message": "余额不足", "response": "余额不足"}
        obj = {"user_id": "789", "raw_message": "/pay Receiver 100"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("转账失败", args[0])
        self.assertIn("余额不足", args[0])

    @patch("get_qqid.get_gamenick")
    @patch("pay.parse_at_or_name")
    def test_pay_at_receiver_not_bound(self, mock_parse, mock_get_gamenick):
        """测试 @的收款人未绑定"""
        mock_get_gamenick.side_effect = lambda qq: "Sender" if qq == "789" else None
        mock_parse.return_value = ("456", None)
        obj = {"user_id": "789", "raw_message": "/pay [CQ:at,qq=456] 100"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("未找到玩家", args[0])

    @patch("pay.transfer_money")
    @patch("get_qqid.get_gamenick")
    @patch("pay.parse_at_or_name")
    def test_pay_at_success(self, mock_parse, mock_get_gamenick, mock_transfer):
        """测试 @玩家转账成功"""
        mock_get_gamenick.side_effect = lambda qq: {"789": "Sender", "456": "Receiver"}[qq]
        mock_parse.return_value = ("456", None)
        mock_transfer.return_value = {"success": True, "message": "转账成功", "response": "OK"}
        obj = {"user_id": "789", "raw_message": "/pay [CQ:at,qq=456] 100"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("转账成功", args[0])

    @patch("get_qqid.get_gamenick")
    def test_pay_invalid_receiver(self, mock_get_gamenick):
        """测试无法识别的收款人"""
        mock_get_gamenick.return_value = "Sender"
        obj = {"user_id": "789", "raw_message": "/pay [CQ:image,file=test.jpg] 100"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("无法识别收款人", args[0])


class TestHandlePrivateMessageBalance(unittest.TestCase):
    """测试私聊 /balance 命令处理"""

    def setUp(self):
        self.send_func = MagicMock()

    @patch("message_handler.is_admin_group_member")
    @patch("xconomy_db.get_player_balance")
    @patch("get_qqid.get_gamenick")
    def test_balance_query_self(self, mock_get_gamenick, mock_balance, mock_admin):
        """查询自己的余额"""
        mock_get_gamenick.return_value = "Steve"
        mock_balance.return_value = {"player": "Steve", "balance": 100.0, "bank_balance": 50.0}
        obj = {"user_id": "789", "raw_message": "/balance"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("Steve", args[0])

    @patch("message_handler.is_admin_group_member")
    @patch("xconomy_db.get_player_balance")
    @patch("get_qqid.get_gamenick")
    def test_balance_query_others_not_admin(self, mock_get_gamenick, mock_balance, mock_admin):
        """非管理群成员查询他人余额时回退查自己"""
        mock_admin.return_value = False
        mock_get_gamenick.return_value = "Steve"
        mock_balance.return_value = {"player": "Steve", "balance": 100.0, "bank_balance": 50.0}
        obj = {"user_id": "789", "raw_message": "/balance OtherPlayer"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("Steve", args[0])

    @patch("message_handler.is_admin_group_member")
    @patch("xconomy_db.get_player_balance")
    def test_balance_query_others_is_admin(self, mock_balance, mock_admin):
        """管理群成员查询他人余额"""
        mock_admin.return_value = True
        mock_balance.return_value = {"player": "Other", "balance": 200.0, "bank_balance": 100.0}
        obj = {"user_id": "789", "raw_message": "/balance Other"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("Other", args[0])


class TestHandlePrivateMessageTransactions(unittest.TestCase):
    """测试私聊 /transactions 命令处理"""

    def setUp(self):
        self.send_func = MagicMock()

    @patch("message_handler.is_admin_group_member")
    @patch("xconomy_db.get_player_transactions")
    @patch("get_qqid.get_gamenick")
    def test_transactions_query_self(self, mock_get_gamenick, mock_trans, mock_admin):
        """查询自己的交易记录"""
        mock_get_gamenick.return_value = "Steve"
        mock_trans.return_value = [{"type": "pay", "amount": 100.0, "target": "Other", "datetime": "2024-01-01"}]
        obj = {"user_id": "789", "raw_message": "/transactions"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()
        args = self.send_func.call_args[0]
        self.assertIn("Steve", args[0])

    @patch("message_handler.is_admin_group_member")
    @patch("xconomy_db.get_player_transactions")
    @patch("get_qqid.get_gamenick")
    def test_transactions_query_others_not_admin(self, mock_get_gamenick, mock_trans, mock_admin):
        """非管理群成员查询他人交易记录时回退查自己"""
        mock_admin.return_value = False
        mock_get_gamenick.return_value = "Steve"
        mock_trans.return_value = []
        obj = {"user_id": "789", "raw_message": "/transactions OtherPlayer"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()

    @patch("message_handler.is_admin_group_member")
    @patch("xconomy_db.get_player_transactions")
    def test_transactions_query_others_is_admin(self, mock_trans, mock_admin):
        """管理群成员查询他人交易记录"""
        mock_admin.return_value = True
        mock_trans.return_value = []
        obj = {"user_id": "789", "raw_message": "/transactions Other"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_called()


class TestFinanceBlockedUsers(unittest.TestCase):
    """测试金融功能屏蔽用户"""

    def setUp(self):
        self.send_func = MagicMock()

    @patch("message_handler.FINANCE_BLOCKED_USERS", ["999"])
    def test_blocked_user_pay(self):
        """被屏蔽用户不能转账，无响应"""
        obj = {"user_id": "999", "raw_message": "/pay Steve 100"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_not_called()

    @patch("message_handler.FINANCE_BLOCKED_USERS", ["999"])
    def test_blocked_user_balance(self):
        """被屏蔽用户不能查余额，无响应"""
        obj = {"user_id": "999", "raw_message": "/balance"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_not_called()

    @patch("message_handler.FINANCE_BLOCKED_USERS", ["999"])
    def test_blocked_user_transactions(self):
        """被屏蔽用户不能查交易记录，无响应"""
        obj = {"user_id": "999", "raw_message": "/transactions"}
        handle_private_message(obj, self.send_func)
        self.send_func.assert_not_called()


class TestHandleGroupMessageFinanceRedirect(unittest.TestCase):
    """测试群内金融命令重定向提示"""

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_group_pay_redirect(self):
        """群内 /pay 应提示去私聊"""
        send_msg = MagicMock()
        obj = {
            "group_id": "123456",
            "user_id": "789",
            "raw_message": "/pay Steve 100",
            "message_id": 1,
            "message_type": "group"
        }
        self._run_async(handle_group_message(obj, send_msg))
        send_msg.assert_called()
        args = send_msg.call_args[0]
        self.assertIn("私聊", args[0])

    def test_group_balance_redirect(self):
        """群内 /balance 应提示去私聊"""
        send_msg = MagicMock()
        obj = {
            "group_id": "123456",
            "user_id": "789",
            "raw_message": "/balance",
            "message_id": 1,
            "message_type": "group"
        }
        self._run_async(handle_group_message(obj, send_msg))
        send_msg.assert_called()
        args = send_msg.call_args[0]
        self.assertIn("私聊", args[0])


class TestHandleGroupMessageOther(unittest.TestCase):
    """测试其他命令"""

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_unauthorized_group(self):
        """测试未授权群组"""
        send_msg = MagicMock()
        obj = {
            "group_id": "999999",
            "user_id": "789",
            "raw_message": "/pay Steve 100",
            "message_id": 1,
            "message_type": "group"
        }
        result = self._run_async(handle_group_message(obj, send_msg))
        self.assertEqual(result, {})
        send_msg.assert_not_called()

    @patch("message_handler.generate_help_card")
    def test_help_command(self, mock_help):
        """测试帮助命令"""
        mock_help.return_value = None
        send_msg = MagicMock()
        obj = {
            "group_id": "123456",
            "user_id": "789",
            "raw_message": "/help",
            "message_id": 1,
            "message_type": "group"
        }
        self._run_async(handle_group_message(obj, send_msg))
        send_msg.assert_called()
        args = send_msg.call_args[0]
        self.assertIn("私聊", args[0])


if __name__ == "__main__":
    unittest.main()
