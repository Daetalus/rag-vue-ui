(function (window, rJS, RSVP) {
  "use strict";

  var SCROLL_THRESHOLD = 80;

  function applyReservePadding(gadget, value) {
    var content = gadget.contentNode;
    if (!content) {
      return;
    }
    content.style.paddingBottom = value > 0 ? String(value) + "px" : "";
  }

  function ensureAnchor(gadget) {
    var content = gadget.contentNode;
    if (!content) {
      return;
    }
    var anchor = content.querySelector('[data-ref="anchor"]');
    if (!anchor) {
      anchor = window.document.createElement("div");
      anchor.dataset.ref = "anchor";
      content.appendChild(anchor);
    }
    anchor.className = gadget.state.anchorClass;
    anchor.setAttribute("aria-hidden", "true");
    gadget.anchorNode = anchor;
  }

  function updateNearBottom(gadget) {
    var element = gadget.containerNode;
    if (!element) {
      return;
    }
    var distance =
      element.scrollHeight -
      element.scrollTop -
      element.clientHeight -
      Math.max(gadget.reservedSpace || 0, 0);
    gadget.isNearBottom = distance <= SCROLL_THRESHOLD;
    if (!gadget.isNearBottom && gadget.reservedSpace !== 0) {
      gadget.reservedSpace = 0;
      applyReservePadding(gadget, 0);
    }
  }

  function scrollToBottom(gadget, options) {
    var element = gadget.containerNode;
    if (!element) {
      return RSVP.resolve();
    }

    var behavior = (options && options.behavior) || "smooth";
    var reserveOption =
      options && typeof options.reserve === "number" ? options.reserve : gadget.reservedSpace || 0;
    var reserve = Math.max(reserveOption, 0);

    if (options && typeof options.reserve === "number") {
      gadget.reservedSpace = reserve;
    }

    applyReservePadding(gadget, reserve);

    var maxScrollTop = Math.max(element.scrollHeight - element.clientHeight, 0);
    var targetTop =
      options && typeof options.top === "number"
        ? Math.max(Math.min(options.top, maxScrollTop), 0)
        : Math.max(maxScrollTop - reserve, 0);

    element.scrollTo({ top: targetTop, behavior: behavior });
    return RSVP.resolve();
  }

  function renderMessages(gadget) {
    var content = gadget.contentNode;
    var template = gadget.templateNode;
    if (!content || !template) {
      return;
    }

    var existingAnchor = content.querySelector('[data-ref="anchor"]');
    content.innerHTML = "";

    gadget.state.messageList.forEach(function (message) {
      var clone = template.content.cloneNode(true);
      var authorNode = clone.querySelector('[data-ref="author"]');
      var textNode = clone.querySelector('[data-ref="text"]');

      if (authorNode) {
        authorNode.textContent = message.author || "";
      }
      if (textNode) {
        textNode.textContent = message.text || "";
      }
      content.appendChild(clone);
    });

    if (existingAnchor) {
      content.appendChild(existingAnchor);
    }
    ensureAnchor(gadget);
  }

  rJS(window)
    .setState({
      containerClass: "flex flex-1 overflow-y-auto",
      contentClass: "flex w-full flex-col",
      anchorClass: "h-px w-full shrink-0 scroll-mt-4",
      messageList: [],
    })
    .ready(function (gadget) {
      return gadget.getElement().then(function (element) {
        gadget.element = element;
        gadget.containerNode = element.querySelector('[data-ref="container"]');
        gadget.contentNode = element.querySelector('[data-ref="content"]');
        gadget.templateNode = element.querySelector("#message-template");
        gadget.anchorNode = element.querySelector('[data-ref="anchor"]');
        gadget.isNearBottom = true;
        gadget.reservedSpace = 0;

        if (gadget.containerNode) {
          gadget.containerNode.className = gadget.state.containerClass;
          gadget.containerNode.addEventListener("scroll", function () {
            updateNearBottom(gadget);
          });
        }

        if (gadget.contentNode) {
          gadget.contentNode.className = gadget.state.contentClass;
        }

        if (gadget.contentNode && window.ResizeObserver) {
          gadget.resizeObserver = new window.ResizeObserver(function () {
            if (gadget.isNearBottom) {
              scrollToBottom(gadget, { behavior: "smooth" });
            }
          });
          gadget.resizeObserver.observe(gadget.contentNode);
        }

        updateNearBottom(gadget);
        ensureAnchor(gadget);
        return scrollToBottom(gadget, { behavior: "auto" });
      });
    })
    .declareMethod("render", function (options) {
      var gadget = this;
      options = options || {};

      gadget.state.containerClass = options.containerClass || gadget.state.containerClass;
      gadget.state.contentClass = options.contentClass || gadget.state.contentClass;
      gadget.state.anchorClass = options.anchorClass || gadget.state.anchorClass;
      gadget.state.messageList = Array.isArray(options.messageList)
        ? options.messageList
        : gadget.state.messageList;

      if (gadget.containerNode) {
        gadget.containerNode.className = gadget.state.containerClass;
      }
      if (gadget.contentNode) {
        gadget.contentNode.className = gadget.state.contentClass;
      }

      renderMessages(gadget);
      return scrollToBottom(gadget, { behavior: "auto" });
    })
    .declareMethod("scrollToBottom", function (options) {
      return scrollToBottom(this, options || {});
    })
    .declareMethod("appendMessage", function (message) {
      var gadget = this;
      gadget.state.messageList = gadget.state.messageList.concat([message || {}]);
      renderMessages(gadget);
      return scrollToBottom(gadget, { behavior: "smooth", reserve: 40 });
    })
    .onStateChange(function (modification_dict) {
      var gadget = this;
      if (modification_dict.hasOwnProperty("messageList")) {
        renderMessages(gadget);
      }
      if (modification_dict.hasOwnProperty("containerClass") && gadget.containerNode) {
        gadget.containerNode.className = gadget.state.containerClass;
      }
      if (modification_dict.hasOwnProperty("contentClass") && gadget.contentNode) {
        gadget.contentNode.className = gadget.state.contentClass;
      }
      if (modification_dict.hasOwnProperty("anchorClass")) {
        ensureAnchor(gadget);
      }
    });
})(window, rJS, RSVP);
