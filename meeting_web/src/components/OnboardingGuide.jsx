import { useState, useEffect, useCallback } from "react";

/**
 * Spotlight 风格新手引导组件
 * 高亮页面上的特定元素并在旁边显示提示
 * @param {string} storageKey - localStorage存储的键名
 * @param {Array} steps - 引导步骤数组 [{targetSelector, title, content, position}]
 */
function OnboardingGuide({ storageKey = "onboarding_seen", steps = [] }) {
  const [isVisible, setIsVisible] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [targetRect, setTargetRect] = useState(null);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });

  // 计算目标元素的位置
  const updateTargetPosition = useCallback(() => {
    const step = steps[currentStep];
    if (!step?.targetSelector) {
      setTargetRect(null);
      return;
    }

    const target = document.querySelector(step.targetSelector);
    if (target) {
      const rect = target.getBoundingClientRect();
      setTargetRect({
        top: rect.top - 8,
        left: rect.left - 8,
        width: rect.width + 16,
        height: rect.height + 16,
      });

      // 检测是否为移动端
      const isMobile = window.innerWidth <= 768;
      
      // 计算tooltip位置
      const position = step.position || "bottom";
      let tooltipTop = 0;
      let tooltipLeft = 0;

      if (isMobile) {
        // 移动端：固定在目标下方或屏幕中央
        tooltipTop = Math.min(rect.bottom + 20, window.innerHeight - 200);
        tooltipLeft = window.innerWidth / 2;
      } else {
        switch (position) {
          case "top":
            tooltipTop = rect.top - 20;
            tooltipLeft = rect.left + rect.width / 2;
            break;
          case "bottom":
            tooltipTop = rect.bottom + 20;
            tooltipLeft = rect.left + rect.width / 2;
            break;
          case "left":
            tooltipTop = rect.top + rect.height / 2;
            tooltipLeft = rect.left - 20;
            break;
          case "right":
            tooltipTop = rect.top + rect.height / 2;
            tooltipLeft = rect.right + 20;
            break;
          default:
            tooltipTop = rect.bottom + 20;
            tooltipLeft = rect.left + rect.width / 2;
        }
      }

      setTooltipPosition({ top: tooltipTop, left: tooltipLeft, position: isMobile ? "bottom" : position });
    } else {
      setTargetRect(null);
    }
  }, [currentStep, steps]);

  useEffect(() => {
    const hasSeen = localStorage.getItem(storageKey);
    if (!hasSeen && steps.length > 0) {
      // 延迟一点确保DOM已渲染
      setTimeout(() => {
        setIsVisible(true);
      }, 500);
    }
  }, [storageKey, steps.length]);

  useEffect(() => {
    if (isVisible) {
      updateTargetPosition();
      window.addEventListener("resize", updateTargetPosition);
      window.addEventListener("scroll", updateTargetPosition);
    }
    return () => {
      window.removeEventListener("resize", updateTargetPosition);
      window.removeEventListener("scroll", updateTargetPosition);
    };
  }, [isVisible, updateTargetPosition]);

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleClose();
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleClose = () => {
    localStorage.setItem(storageKey, "true");
    setIsVisible(false);
  };

  if (!isVisible || steps.length === 0) return null;

  const step = steps[currentStep];
  const positionClass = tooltipPosition.position || "bottom";

  return (
    <div className="spotlight-overlay">
      {/* 暗色遮罩层，使用clip-path挖空目标区域 */}
      <div
        className="spotlight-mask"
        onClick={handleClose}
        style={
          targetRect
            ? {
                clipPath: `polygon(
                  0% 0%, 
                  0% 100%, 
                  ${targetRect.left}px 100%, 
                  ${targetRect.left}px ${targetRect.top}px, 
                  ${targetRect.left + targetRect.width}px ${targetRect.top}px, 
                  ${targetRect.left + targetRect.width}px ${targetRect.top + targetRect.height}px, 
                  ${targetRect.left}px ${targetRect.top + targetRect.height}px, 
                  ${targetRect.left}px 100%, 
                  100% 100%, 
                  100% 0%
                )`,
              }
            : {}
        }
      />

      {/* 高亮边框 */}
      {targetRect && (
        <div
          className="spotlight-highlight"
          style={{
            top: targetRect.top,
            left: targetRect.left,
            width: targetRect.width,
            height: targetRect.height,
          }}
        />
      )}

      {/* 提示框 */}
      <div
        className={`spotlight-tooltip ${positionClass}`}
        style={{
          top: tooltipPosition.top,
          left: tooltipPosition.left,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 进度指示器 */}
        <div className="spotlight-progress">
          {steps.map((_, index) => (
            <div
              key={index}
              className={`progress-dot ${index === currentStep ? "active" : ""} ${index < currentStep ? "completed" : ""}`}
            />
          ))}
        </div>

        <div className="spotlight-content">
          <h3 className="spotlight-title">{step.title}</h3>
          <p className="spotlight-text">{step.content}</p>
        </div>

        <div className="spotlight-actions">
          <button className="btn-skip" onClick={handleClose}>
            跳过
          </button>
          <div className="btn-group">
            {currentStep > 0 && (
              <button className="btn btn-secondary" onClick={handlePrev}>
                上一步
              </button>
            )}
            <button className="btn btn-primary" onClick={handleNext}>
              {currentStep === steps.length - 1 ? "完成" : "下一步"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OnboardingGuide;
