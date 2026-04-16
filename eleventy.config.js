export default function(eleventyConfig) {
  eleventyConfig.addPassthroughCopy({ "chile_protest_config.json": "chile_protest_config.json" });
  return {
    dir: {
      input: "src",
      output: "_site",
      includes: "_includes"
    }
  };
};
