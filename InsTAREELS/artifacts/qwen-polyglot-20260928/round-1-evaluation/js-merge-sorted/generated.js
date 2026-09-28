const {merge} = require('lodash');

module.exports = (input) => {
  const left = input.left;
  const right = input.right;
  return merge(left, right);
};