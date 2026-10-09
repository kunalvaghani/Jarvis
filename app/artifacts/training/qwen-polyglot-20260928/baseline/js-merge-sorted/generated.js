const {merge} = require('lodash');

module.exports = (input) => {
  return merge(input.left, input.right);
};