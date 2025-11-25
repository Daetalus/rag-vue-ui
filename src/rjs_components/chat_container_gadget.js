/*global window, rJS, RSVP */
(function (window, rJS, RSVP) {
  "use strict";

  // ChatScrollOptions 的 JS 版本：
  // { top?: number, reserve?: number, behavior?: "auto" | "smooth" }
  function computeScrollTop(container, options) {
    var reserve = (options && options.reserve) || 32;
    // 如果显式指定 top，则直接使用；否则滚到底部
    if (options && typeof options.top === "number") {
      return options.top;
    }
    return (
      container.scrollHeight - container.clientHeight - reserve
    );
  }

  rJS(window)
    // ready: 初始化类似 ChatContainerContext 的“上下文”
    .ready(function (gadget) {
      var element = gadget.element;

      gadget.state = gadget.state || {};

      // 对应 Vue 里的 containerRef / contentRef / ScrollAnchor
      gadget.state.container =
        element.querySelector('[data-role="chat-root"]');
      gadget.state.content =
        element.querySelector('[data-role="chat-content"]');
      gadget.state.anchor =
        element.querySelector('[data-role="chat-scroll-anchor"]');
      gadget.state.inputForm =
        element.querySelector('[data-role="chat-input"]');
      gadget.state.isNearBottom = true;

      // 监听容器滚动，判断是否靠近底部
      function onScroll() {
        var c = gadget.state.container;
        if (!c) {
          return;
        }
        var distance =
          c.scrollHeight - c.scrollTop - c.clientHeight;
        gadget.state.isNearBottom = distance < 64; // 接近底部阈值
      }

      if (gadget.state.container) {
        gadget.state.container.addEventListener(
          "scroll",
          onScroll,
          false
        );
      }

      // 简单的表单提交 -> appendMessage
      if (gadget.state.inputForm) {
        gadget.state.inputForm.addEventListener(
          "submit",
          function (evt) {
            var input = gadget.state.inputForm.querySelector(
              'input[name="message"]'
            );
            evt.preventDefault();
            if (input && input.value.trim()) {
              gadget.appendMessage(input.value.trim());
              input.value = "";
            }
          },
          false
        );
      }

      // 记录清理函数
      gadget.state._cleanup = function () {
        if (gadget.state.container) {
          gadget.state.container.removeEventListener(
            "scroll",
            onScroll,
            false
          );
        }
      };
    })

    // 模拟原来的 scrollToBottom(context: ChatScrollOptions)
    .declareMethod("scrollToBottom", function (options) {
      var container = this.state.container;
      var targetTop;

      if (!container) {
        return;
      }

      targetTop = computeScrollTop(container, options);

      var behavior =
        (options && options.behavior) || "auto";

      if (container.scrollTo) {
        container.scrollTo({
          top: targetTop,
          behavior: behavior
        });
      } else {
        container.scrollTop = targetTop;
      }
    })

    // 简单的 appendMessage，用于测试 ChatContainerContent + auto-scroll
    .declareMethod("appendMessage", function (text) {
      var gadget = this;
      var content = gadget.state.content;
      var message;

      if (!content) {
        return;
      }

      message = window.document.createElement("div");
      message.className = "chat-message";
      message.textContent = text;

      content.appendChild(message);

      // 如果当前靠近底部，就自动滚动到底
      if (gadget.state.isNearBottom) {
        return gadget.scrollToBottom({
          behavior: "smooth",
          reserve: 16
        });
      }
      return;
    })

    // 可选：在 gadget 生命周期结束时清理监听（示意）
    .declareService(function () {
      var gadget = this;

      // 这里启动一个“保持运行”的 promise，直到页面卸载。
      return new RSVP.Promise(function () {
        // 不做额外事，仅占位；
        // 如果你要用 RSVP.Queue 等更复杂模式，可以在这里扩展。
      }).fail(function () {
        if (
          gadget.state &&
          typeof gadget.state._cleanup === "function"
        ) {
          gadget.state._cleanup();
        }
      });
    });
})(window, rJS, RSVP);

