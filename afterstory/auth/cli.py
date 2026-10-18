"""Local administrator commands; credentials never pass through shell arguments."""

import argparse
import getpass
import sys

from afterstory.auth.service import AuthService
from afterstory.config import Settings
from afterstory.database import make_sessions


def main(argv=None):
    parser = argparse.ArgumentParser(description="AfterStory account administration")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("create", "reset-password"):
        commands.add_parser(name).add_argument("username")
    commands.add_parser("invite-create").add_argument("--days", type=int, default=7)
    commands.add_parser("invite-revoke")
    args = parser.parse_args(argv)
    password = None
    code = None
    if args.command in {"create", "reset-password"}:
        password = getpass.getpass("密码（至少 12 个字符）：")
        if password != getpass.getpass("再次输入密码："):
            print("两次密码不一致", file=sys.stderr)
            return 2
    elif args.command == "invite-revoke":
        code = getpass.getpass("要撤销的邀请码：")
    engine, sessions = make_sessions(Settings())
    try:
        auth = AuthService(sessions)
        if args.command == "create":
            user_id = auth.create_account(args.username, password)
            print(f"账号已创建：{args.username}（用户 ID：{user_id}）")
        elif args.command == "reset-password":
            auth.reset_password(args.username, password)
            print(f"密码已重设：{args.username}；旧登录会话已失效")
        elif args.command == "invite-create":
            invite_code, expires_at = auth.issue_invite(args.days)
            print(f"邀请码（仅显示一次）：{invite_code}")
            print(f"有效至：{expires_at.isoformat()}")
        else:
            auth.revoke_invite(code)
            print("邀请码已撤销")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
