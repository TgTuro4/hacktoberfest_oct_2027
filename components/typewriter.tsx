"use client";

import { useEffect, useState } from "react";

// Same loop as immortalWebDev/Typewriter-effect: type, hold, delete, hold, next word.
const WORDS = ["Events", "Groups", "Fun", "Everything"];
const TYPE_MS = 100;
const DELETE_MS = 60;
const HOLD_MS = 500;
const LAST_HOLD_MS = HOLD_MS * 2; // "Everything" stays up twice as long
const FINAL = WORDS.length - 1;

/**
 * Cycles through WORDS. Starts on the full last word so the first paint matches the server
 * render and the headline never flashes empty. Reduced-motion users just see "Everything".
 */
export function Typewriter() {
  const [word, setWord] = useState(FINAL);
  const [length, setLength] = useState(WORDS[FINAL].length);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let index = FINAL;
    let chars = WORDS[FINAL].length;
    let typing = false;
    let timer: ReturnType<typeof setTimeout>;

    function tick() {
      const current = WORDS[index];
      let delay: number;
      if (typing) {
        chars++;
        setLength(chars);
        if (chars >= current.length) {
          typing = false;
          delay = index === FINAL ? LAST_HOLD_MS : HOLD_MS;
        } else delay = TYPE_MS;
      } else {
        chars--;
        setLength(chars);
        if (chars <= 0) {
          typing = true;
          index = (index + 1) % WORDS.length;
          setWord(index);
          delay = HOLD_MS / 2;
        } else delay = DELETE_MS;
      }
      timer = setTimeout(tick, delay);
    }
    // First deletion begins after the opening word has been held the longer time.
    timer = setTimeout(tick, LAST_HOLD_MS);
    return () => clearTimeout(timer);
  }, []);

  return <span className="type-word" aria-hidden="true">{WORDS[word].slice(0, length) || "​"}<span className="type-caret" /></span>;
}
