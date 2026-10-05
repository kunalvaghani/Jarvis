"""Windows-MCP UIA pattern subset. Author: yinkaisheng.
Original UIAutomation library: Apache-2.0; Windows-MCP changes: MIT.
See source-manifest.json and licenses/. Selected class methods are intact except
HRESULT success normalization (comtypes can return None) and a zero default wait.
SelectionContainer (unvendored Control dependency) and SetToggleState (may issue
multiple Toggle calls) are omitted. No framework/server is imported.
"""
from __future__ import annotations
import time
from typing import List, TYPE_CHECKING
S_OK = 0
OPERATION_WAIT_TIME = 0

class ExpandCollapsePattern:
    def __init__(self, pattern=None):
        """Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nn-uiautomationclient-iuiautomationexpandcollapsepattern"""
        self.pattern = pattern

    @property
    def ExpandCollapseState(self) -> int:
        """
        Property ExpandCollapseState.
        Call IUIAutomationExpandCollapsePattern::get_CurrentExpandCollapseState.
        Return int, a value in class ExpandCollapseState.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationexpandcollapsepattern-get_currentexpandcollapsestate
        """
        return self.pattern.CurrentExpandCollapseState

    def Collapse(self, waitTime: float = OPERATION_WAIT_TIME) -> bool:
        """
        Call IUIAutomationExpandCollapsePattern::Collapse.
        waitTime: float.
        Return bool, True if succeed otherwise False.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationexpandcollapsepattern-collapse
        """
        try:
            ret = self.pattern.Collapse() in (None, S_OK)
            time.sleep(waitTime)
            return ret
        except Exception:
            pass
        return False

    def Expand(self, waitTime: float = OPERATION_WAIT_TIME) -> bool:
        """
        Call IUIAutomationExpandCollapsePattern::Expand.
        waitTime: float.
        Return bool, True if succeed otherwise False.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationexpandcollapsepattern-expand
        """
        try:
            ret = self.pattern.Expand() in (None, S_OK)
            time.sleep(waitTime)
            return ret
        except Exception:
            pass
        return False

class InvokePattern:
    def __init__(self, pattern=None):
        """Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nn-uiautomationclient-iuiautomationinvokepattern"""
        self.pattern = pattern

    def Invoke(self, waitTime: float = OPERATION_WAIT_TIME) -> bool:
        """
        Call IUIAutomationInvokePattern::Invoke.
        Invoke the action of a control, such as a button click.
        waitTime: float.
        Return bool, True if succeed otherwise False.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationinvokepattern-invoke
        """
        ret = self.pattern.Invoke() in (None, S_OK)
        time.sleep(waitTime)
        return ret

class ScrollPattern:
    def __init__(self, pattern=None):
        """Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nn-uiautomationclient-iuiautomationscrollpattern"""
        self.pattern = pattern

    @property
    def HorizontallyScrollable(self) -> bool:
        """
        Property HorizontallyScrollable.
        Call IUIAutomationScrollPattern::get_CurrentHorizontallyScrollable.
        Return bool, indicates whether the element can scroll horizontally.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationscrollpattern-get_currenthorizontallyscrollable
        """
        return bool(self.pattern.CurrentHorizontallyScrollable)

    @property
    def HorizontalScrollPercent(self) -> float:
        """
        Property HorizontalScrollPercent.
        Call IUIAutomationScrollPattern::get_CurrentHorizontalScrollPercent.
        Return float, the horizontal scroll position.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationscrollpattern-get_currenthorizontalscrollpercent
        """
        return self.pattern.CurrentHorizontalScrollPercent

    @property
    def HorizontalViewSize(self) -> float:
        """
        Property HorizontalViewSize.
        Call IUIAutomationScrollPattern::get_CurrentHorizontalViewSize.
        Return float, the horizontal size of the viewable region of a scrollable element.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationscrollpattern-get_currenthorizontalviewsize
        """
        return self.pattern.CurrentHorizontalViewSize

    @property
    def VerticallyScrollable(self) -> bool:
        """
        Property VerticallyScrollable.
        Call IUIAutomationScrollPattern::get_CurrentVerticallyScrollable.
        Return bool, indicates whether the element can scroll vertically.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationscrollpattern-get_currentverticallyscrollable
        """
        return bool(self.pattern.CurrentVerticallyScrollable)

    @property
    def VerticalScrollPercent(self) -> float:
        """
        Property VerticalScrollPercent.
        Call IUIAutomationScrollPattern::get_CurrentVerticalScrollPercent.
        Return float, the vertical scroll position.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationscrollpattern-get_currentverticalscrollpercent
        """
        return self.pattern.CurrentVerticalScrollPercent

    @property
    def VerticalViewSize(self) -> float:
        """
        Property VerticalViewSize.
        Call IUIAutomationScrollPattern::get_CurrentVerticalViewSize.
        Return float, the vertical size of the viewable region of a scrollable element.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationscrollpattern-get_currentverticalviewsize
        """
        return self.pattern.CurrentVerticalViewSize

    def Scroll(
        self,
        horizontalAmount: int,
        verticalAmount: int,
        waitTime: float = OPERATION_WAIT_TIME,
    ) -> bool:
        """
        Call IUIAutomationScrollPattern::Scroll.
        Scroll the visible region of the content area horizontally and vertically.
        horizontalAmount: int, a value in ScrollAmount.
        verticalAmount: int, a value in ScrollAmount.
        waitTime: float.
        Return bool, True if succeed otherwise False.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationscrollpattern-scroll
        """
        ret = self.pattern.Scroll(horizontalAmount, verticalAmount) in (None, S_OK)
        time.sleep(waitTime)
        return ret

    def SetScrollPercent(
        self,
        horizontalPercent: float,
        verticalPercent: float,
        waitTime: float = OPERATION_WAIT_TIME,
    ) -> bool:
        """
        Call IUIAutomationScrollPattern::SetScrollPercent.
        Set the horizontal and vertical scroll positions as a percentage of the total content area within the UI Automation element.
        horizontalPercent: float or int, a value in [0, 100] or ScrollPattern.NoScrollValue(-1) if no scroll.
        verticalPercent: float or int, a value  in [0, 100] or ScrollPattern.NoScrollValue(-1) if no scroll.
        waitTime: float.
        Return bool, True if succeed otherwise False.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationscrollpattern-setscrollpercent
        """
        ret = self.pattern.SetScrollPercent(horizontalPercent, verticalPercent) in (None, S_OK)
        time.sleep(waitTime)
        return ret

class SelectionItemPattern:
    def __init__(self, pattern=None):
        """Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nn-uiautomationclient-iuiautomationselectionitempattern"""
        self.pattern = pattern

    def AddToSelection(self, waitTime: float = OPERATION_WAIT_TIME) -> bool:
        """
        Call IUIAutomationSelectionItemPattern::AddToSelection.
        Add the current element to the collection of selected items.
        waitTime: float.
        Return bool, True if succeed otherwise False.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationselectionitempattern-addtoselection
        """
        ret = self.pattern.AddToSelection() in (None, S_OK)
        time.sleep(waitTime)
        return ret

    @property
    def IsSelected(self) -> bool:
        """
        Property IsSelected.
        Call IUIAutomationScrollPattern::get_CurrentIsSelected.
        Return bool, indicates whether this item is selected.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationscrollpattern-get_currentisselected
        """
        return bool(self.pattern.CurrentIsSelected)

    def RemoveFromSelection(self, waitTime: float = OPERATION_WAIT_TIME) -> bool:
        """
        Call IUIAutomationSelectionItemPattern::RemoveFromSelection.
        Remove this element from the selection.
        waitTime: float.
        Return bool, True if succeed otherwise False.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationselectionitempattern-removefromselection
        """
        ret = self.pattern.RemoveFromSelection() in (None, S_OK)
        time.sleep(waitTime)
        return ret

    def Select(self, waitTime: float = OPERATION_WAIT_TIME) -> bool:
        """
        Call IUIAutomationSelectionItemPattern::Select.
        Clear any selected items and then select the current element.
        waitTime: float.
        Return bool, True if succeed otherwise False.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationselectionitempattern-select
        """
        ret = self.pattern.Select() in (None, S_OK)
        time.sleep(waitTime)
        return ret

class TogglePattern:
    def __init__(self, pattern=None):
        """Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nn-uiautomationclient-iuiautomationtogglepattern"""
        self.pattern = pattern

    @property
    def ToggleState(self) -> int:
        """
        Property ToggleState.
        Call IUIAutomationTogglePattern::get_CurrentToggleState.
        Return int, a value in class `ToggleState`, the state of the control.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationtogglepattern-get_currenttogglestate
        """
        return self.pattern.CurrentToggleState

    def Toggle(self, waitTime: float = OPERATION_WAIT_TIME) -> bool:
        """
        Call IUIAutomationTogglePattern::Toggle.
        Cycle through the toggle states of the control.
        waitTime: float.
        Return bool, True if succeed otherwise False.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationtogglepattern-toggle
        """
        ret = self.pattern.Toggle() in (None, S_OK)
        time.sleep(waitTime)
        return ret

class ValuePattern:
    def __init__(self, pattern=None):
        """Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nn-uiautomationclient-iuiautomationvaluepattern"""
        self.pattern = pattern

    @property
    def IsReadOnly(self) -> bool:
        """
        Property IsReadOnly.
        Call IUIAutomationTransformPattern2::IUIAutomationValuePattern::get_CurrentIsReadOnly.
        Return bool, indicates whether the value of the element is read-only.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationvaluepattern-get_currentisreadonly
        """
        return bool(self.pattern.CurrentIsReadOnly)

    @property
    def Value(self) -> str:
        """
        Property Value.
        Call IUIAutomationTransformPattern2::IUIAutomationValuePattern::get_CurrentValue.
        Return str, the value of the element.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationvaluepattern-get_currentvalue
        """
        return self.pattern.CurrentValue

    def SetValue(self, value: str, waitTime: float = OPERATION_WAIT_TIME) -> bool:
        """
        Call IUIAutomationTransformPattern2::IUIAutomationValuePattern::SetValue.
        Set the value of the element.
        value: str.
        waitTime: float.
        Return bool, True if succeed otherwise False.
        Refer https://docs.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationvaluepattern-setvalue
        """
        ret = self.pattern.SetValue(value) in (None, S_OK)
        time.sleep(waitTime)
        return ret
