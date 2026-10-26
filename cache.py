"""L1 data cache model.

* Direct-mapped (ways=1) or N-way set-associative, LRU replacement.
* Write-allocate, write-through (kept simple: a write hits or misses exactly
  like a read, so it costs the same).
* Only RAM accesses go through the cache. Phone I/O registers are uncached.

Address split:   | tag | set index | block offset |
"""


class Cache:
    def __init__(self, size=256, block=16, ways=1, hit_time=1):
        if block < 4 or block % 4:
            raise ValueError("Block size must be a multiple of 4 bytes")
        if size % (block * ways) or size // (block * ways) < 1:
            raise ValueError("Cache size must be a multiple of block size x ways")
        self.size, self.block, self.ways, self.hit_time = size, block, ways, hit_time
        self.num_sets = size // (block * ways)
        self.sets = [[{"valid": False, "tag": None, "used": 0} for _ in range(ways)]
                     for _ in range(self.num_sets)]
        self.tick = 0
        self.hits = 0
        self.misses = 0
        self.log = []

    # ---- statistics ----
    @property
    def accesses(self):
        return self.hits + self.misses

    @property
    def hit_rate(self):
        return self.hits / self.accesses if self.accesses else 0.0

    @property
    def miss_rate(self):
        return 1 - self.hit_rate if self.accesses else 0.0

    def amat(self, mem_latency):
        """Average memory access time in cycles (hit costs hit_time, miss costs mem_latency)."""
        return self.hit_rate * self.hit_time + self.miss_rate * mem_latency

    # ---- access ----
    def access(self, addr, is_write=False, ref=None):
        """Look up addr. Returns True on a hit, False on a miss (line is then filled)."""
        block_no = addr // self.block
        idx = block_no % self.num_sets
        tag = block_no // self.num_sets
        self.tick += 1
        ways = self.sets[idx]
        hit = False
        for line in ways:
            if line["valid"] and line["tag"] == tag:
                line["used"] = self.tick
                hit = True
                break
        if hit:
            self.hits += 1
        else:
            self.misses += 1
            victim = next((l for l in ways if not l["valid"]), None)
            if victim is None:
                victim = min(ways, key=lambda l: l["used"])       # LRU
            victim.update(valid=True, tag=tag, used=self.tick)
        self.log.append({
            "#": len(self.log) + 1,
            "Instruction": ref,
            "Address": f"{addr:#06x}",
            "Operation": "write" if is_write else "read",
            "Set": idx,
            "Tag": tag,
            "Result": "HIT" if hit else "MISS",
        })
        return hit

    # ---- view for the interface ----
    def snapshot(self):
        lines = []
        for s, ways in enumerate(self.sets):
            for w, line in enumerate(ways):
                if line["valid"]:
                    base = (line["tag"] * self.num_sets + s) * self.block
                    lines.append({"Set": s, "Way": w, "Tag": line["tag"],
                                  "Memory block": f"{base:#06x} - {base + self.block - 1:#06x}"})
        return {"lines": lines, "accesses": self.accesses, "hits": self.hits,
                "misses": self.misses, "last": self.log[-1] if self.log else None}

    def describe(self):
        kind = "direct-mapped" if self.ways == 1 else f"{self.ways}-way set-associative"
        return (f"{self.size} B, {self.block} B blocks, {kind}, "
                f"{self.num_sets} sets, LRU, write-allocate / write-through")
