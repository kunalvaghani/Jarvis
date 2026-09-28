function solve({ items, size }) { if (!Number.isInteger(size) || size < 1) throw new RangeError('size must be positive'); const result = []; for (let i = 0; i < items.length; i += size) result.push(items.slice(i, i + size)); return result; }
module.exports = { solve };
