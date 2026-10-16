"""Local administrator commands; credentials never pass through shell arguments."""

import argparse
import getpass
import sys

from afterstory.auth import AuthService
from afterstory.config import Settings
from afterstory.database import make_sessions


def main(argv=None):
    parser = argparse.ArgumentParser(description="AfterStory account administration")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("create", "reset-password"):
        commands.add_parser(name).add_argument("username")
    args = parser.parse_args(argv)
    password = getpass.getpass("密码（至少 12 个字符）：")
    if password != getpass.getpass("再次输入密码："):
        print("两次密码不一致", file=sys.stderr)
        return 2
    engine, sessions = make_sessions(Settings())
    try:
        auth = AuthService(sessions)
        if args.command == "create":
            user_id = auth.create_account(args.username, password)
            print(f"账号已创建：{args.username}（用户 ID：{user_id}）")
        else:
            auth.reset_password(args.username, password)
            print(f"密码已重设：{args.username}；旧登录会话已失效")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
