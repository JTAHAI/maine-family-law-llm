/*
 * Shared, dependency-free presentation primitives for the production local
 * workbench.  This file intentionally contains no matter data, network calls,
 * or DOM mutation.  It can therefore be tested independently of the large
 * workbench controller and loaded before it in both source and frozen builds.
 */
(function attachMaineWorkbenchComponents(root) {
  'use strict';

  function text(value) {
    return String(value == null ? '' : value);
  }

  function searchableText(value) {
    return text(value)
      .toLocaleLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, ' ')
      .trim()
      .replace(/\s+/g, ' ');
  }

  /**
   * Return commands in deterministic display order and preserve the first
   * encountered group order.  Command handlers are left on the original
   * objects; this routine never executes a command.
   */
  function filterAndGroupCommands(commands, filter) {
    const needle = searchableText(filter);
    const items = Array.isArray(commands) ? commands.filter((command) => {
      const candidate = command && typeof command === 'object' ? command : {};
      const haystack = searchableText([candidate.group, candidate.label, candidate.hint, candidate.aliases]
        .map(text)
        .join(' '));
      return !needle || haystack.includes(needle);
    }) : [];
    const groupsByName = new Map();
    const groups = [];
    items.forEach((command, index) => {
      const name = text(command.group) || 'Other';
      let group = groupsByName.get(name);
      if (!group) {
        group = {name, commands: []};
        groupsByName.set(name, group);
        groups.push(group);
      }
      group.commands.push({command, index});
    });
    return {items, groups};
  }

  /** Clamp a listbox index for non-wrapping keyboard navigation. */
  function moveListIndex(currentIndex, length, direction) {
    const count = Number.isFinite(Number(length)) ? Math.max(0, Math.trunc(Number(length))) : 0;
    if (!count) return 0;
    const current = Number.isFinite(Number(currentIndex))
      ? Math.min(Math.max(0, Math.trunc(Number(currentIndex))), count - 1)
      : 0;
    const delta = Number.isFinite(Number(direction)) ? Math.trunc(Number(direction)) : 0;
    return Math.min(Math.max(0, current + delta), count - 1);
  }

  /**
   * Keep only the currently useful portion of a filtered collection in the
   * DOM. Callers retain the complete in-memory list for search, source lookup,
   * and export; no item is discarded or silently changed.
   */
  function filterAndWindowItems(items, filter, limit, textForItem) {
    const allItems = Array.isArray(items) ? items : [];
    const needle = text(filter).trim().toLocaleLowerCase();
    const project = typeof textForItem === 'function' ? textForItem : (item) => item;
    const matchingItems = allItems.filter((item) => !needle || text(project(item)).toLocaleLowerCase().includes(needle));
    const requestedLimit = Number.isFinite(Number(limit)) ? Math.max(1, Math.trunc(Number(limit))) : 1;
    return {
      allCount: allItems.length,
      matchingCount: matchingItems.length,
      visibleItems: matchingItems.slice(0, requestedLimit),
      remainingCount: Math.max(0, matchingItems.length - requestedLimit),
    };
  }

  root.MaineWorkbenchComponents = Object.freeze({
    filterAndGroupCommands,
    moveListIndex,
    filterAndWindowItems,
  });
}(window));
