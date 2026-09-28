function merge(a, b) {
  return [...new Set([...a, ...b])];
}

module.exports = {solve: merge};
```