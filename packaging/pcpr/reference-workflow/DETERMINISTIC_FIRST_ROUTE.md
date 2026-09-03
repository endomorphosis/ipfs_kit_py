# PCPR-063 Kit deterministic-first route binding

These files bind the Kit-owned hermetic current root to the
Accelerate-owned deterministic-first route. Kit does not remint the
pack CID, does not execute the route, and does not decide semantic
soundness.

- `cpython312/reference.deterministic-first-route.binding.json` binds
  the Kit current root to the Accelerate route. Exact commit and tree
  are bound by the PCPR-063 receipt `current_tree_binding`.
- Execution is owned by Accelerate. Bounded patch remains PCPR-064.
  Selected tests remain PCPR-065.
- Missing a live Quack-fenced session emits operator-blocking task
  `pcpr-063-operator-live-deterministic-route`.

Sealed validation PATH is exactly `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin`.
