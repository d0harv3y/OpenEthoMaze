/**
 * Simple multiple-choice quiz — one question at a time feedback.
 * data-quiz on container; each .quiz-item needs data-answer index (0-based).
 */
(function () {
  function initQuiz(container) {
    container.querySelectorAll(".quiz-item").forEach(function (item) {
      var answer = parseInt(item.getAttribute("data-answer"), 10);
      var feedback = item.querySelector(".quiz-feedback");
      var buttons = item.querySelectorAll(".quiz-options button");

      buttons.forEach(function (btn, idx) {
        btn.addEventListener("click", function () {
          if (item.classList.contains("answered")) return;
          item.classList.add("answered");
          buttons.forEach(function (b) {
            b.disabled = true;
          });
          if (idx === answer) {
            btn.classList.add("correct");
            feedback.textContent = btn.getAttribute("data-ok") || "Correct.";
            feedback.style.color = "var(--correct)";
          } else {
            btn.classList.add("wrong");
            buttons[answer].classList.add("correct");
            feedback.textContent =
              btn.getAttribute("data-bad") || "Not quite — see highlighted answer.";
            feedback.style.color = "var(--wrong)";
          }
        });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-quiz]").forEach(initQuiz);
  });
})();
