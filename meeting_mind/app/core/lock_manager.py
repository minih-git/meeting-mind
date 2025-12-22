import asyncio
from meeting_mind.app.core.logger import logger


class GlobalLockManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalLockManager, cls).__new__(cls)
            cls._instance.lock = asyncio.Lock()
            # 追踪当前持有锁的 session_id，方便调试
            cls._instance.current_owner = None
        return cls._instance

    def try_acquire(self, owner_id: str) -> bool:
        """
        尝试获取锁。
        如果获取成功，返回 True。
        如果已被占用，返回 False。
        注意：asyncio.Lock.acquire() 是会等待的，我们需要非阻塞的行为。
        但 asyncio.Lock 没有 try_acquire 方法 (Python 3.10+ 才有 locked() 但不可靠)。

        正确做法是使用 locked() 检查状态，但这有竞态条件。
        更好的做法是使用 atomic check-and-set 逻辑，但这里 asyncio 是单线程事件循环，
        只要没有 await，locked() 检查和 acquire 之间不会被抢占。
        """
        if self.lock.locked():
            return False

        # 这里虽然有点 hack，但在单线程 event loop 中是安全的，只要中间没有 await
        # 为了严谨，我们可以用 acquire_nowait 模式，但 asyncio.Lock 没暴露这个。
        # 替代方案：

        # 实际上 asyncio.Lock.acquire 是个 coroutine，必须 awiat。
        # 我们可以维护一个简单的 bool flag，配合 lock 使用，或者直接只用 bool flag (因为 asyncio 是单线程)
        # 但为了未来扩展性，我们还是保留 Lock 对象，但主要逻辑依赖内部状态 check。

        # 修正：asyncio 是单线程的，所以简单的 bool 检查是原子的（只要没有 await 切换）。
        # 但为了配合 Lock 的语义 (比如未来可能需要在某些地方 wait)，我们还是尝试获取。

        # 然而，asyncio.Lock 在 acquire 时如果锁住了会挂起。
        # 我们想要的是 "try_lock"，即失败立即返回 false。

        if self.lock.locked():
            return False

        # 这是一个小 trick，因为 locked() 为 false 时，acquire 不会阻塞 (除非有其他 waiter，但我们这里场景简单)
        # 然而为了绝对安全，我们不直接 call acquire()，因为它必须被 await，而 await 就会交出控制权。
        # 如果我们不想 await，就不能用标准的 asyncio.Lock 来做 atomic try_lock。

        # 鉴于我们的需求是 "不允许发起第二个录音"，我们可以简单地使用一个原子变量。
        # 在 asyncio 中，变量赋值是原子的。

        # 让我们重新实现一下，不依赖 asyncio.Lock 的复杂性，直接用标记位即可。
        pass

    # 重新设计：简单标记位版本，足够满足 asyncio 场景


class SimpleGlobalLock:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SimpleGlobalLock, cls).__new__(cls)
            cls._instance._is_busy = False
            cls._instance.current_owner = None
        return cls._instance

    def try_acquire(self, owner_id: str) -> bool:
        if self._is_busy:
            return False

        self._is_busy = True
        self.current_owner = owner_id
        logger.info(f"Global lock acquired by {owner_id}")
        return True

    def release(self, owner_id: str):
        if not self._is_busy:
            logger.warning(f"Attempt to release lock by {owner_id} but lock is free")
            return

        if self.current_owner != owner_id:
            logger.warning(
                f"Attempt to release lock by {owner_id} but owner is {self.current_owner}"
            )
            # 这里即使不是 owner 也不要强制释放，防止错误释放别人的锁
            # 但考虑到我们的场景，如果 session 结束了，为了防止死锁，可能需要策略。
            # 目前严格匹配 owner。
            return

        self._is_busy = False
        self.current_owner = None
        logger.info(f"Global lock released by {owner_id}")

    def is_locked(self) -> bool:
        return self._is_busy


global_lock = SimpleGlobalLock()
