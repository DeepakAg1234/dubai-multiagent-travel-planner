import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  englishFromTranslate,
  guessLanguage,
  isEnglishReading,
  needsTranslation,
  readingPlan,
  translateRequest,
} from "./translate.ts";

describe("needsTranslation", () => {
  it("leaves English on the local reader and sends Indic script onward", () => {
    assert.equal(needsTranslation("Four days in Dubai"), false);
    assert.equal(needsTranslation("चार दिन दुबई"), true);
    assert.equal(needsTranslation("நான்கு நாட்கள்"), true);
    assert.equal(needsTranslation("چار دن"), true);
  });
});

describe("translate request", () => {
  it("asks Mayura to detect the language and return English", () => {
    const body = translateRequest("  चार दिन  ", "mayura:v1", "auto");
    assert.equal(body.input, "चार दिन");
    assert.equal(body.source_language_code, "auto");
    assert.equal(body.target_language_code, "en-IN");
    assert.equal(body.model, "mayura:v1");
    assert.equal(body.mode, "modern-colloquial");
  });

  it("uses a script guess for Sarvam-Translate", () => {
    assert.equal(guessLanguage("வணக்கம்"), "ta-IN");
    assert.equal(guessLanguage("नमस्ते"), "hi-IN");
    const body = translateRequest("வணக்கம்", "sarvam-translate:v1", "ta-IN");
    assert.equal(body.mode, "formal");
    assert.equal(body.source_language_code, "ta-IN");
  });

  it("reads English directly and translates every other script", () => {
    assert.deepEqual(readingPlan("Four days in Dubai", "", ""), { action: "extract", text: "Four days in Dubai" });
    assert.deepEqual(readingPlan("चार दिन दुबई", "", ""), { action: "translate" });
    assert.deepEqual(readingPlan("चार दिन दुबई", "  four days in Dubai  ", "चार दिन दुबई"), {
      action: "use-english",
      text: "four days in Dubai",
    });
    assert.deepEqual(readingPlan("चार दिन और समुद्र", "four days in Dubai", "चार दिन दुबई"), { action: "translate" });
  });

  it("accepts an English translation and rejects one that is still Indic", () => {
    assert.equal(isEnglishReading(" four days in Dubai "), true);
    assert.equal(isEnglishReading("चार दिन"), false);
    assert.equal(isEnglishReading("   "), false);
  });

  it("reads the translated text and ignores a bad body", () => {
    assert.equal(englishFromTranslate({ translated_text: "  four days  " }), "four days");
    assert.equal(englishFromTranslate({ translated_text: "  " }), "");
    assert.equal(englishFromTranslate(null), "");
  });
});
