!macro customWelcomePage
  !insertmacro skipPageIfUpdated
  !define MUI_WELCOMEPAGE_TITLE "Welcome to FrameGrab ${VERSION}"
  !define MUI_WELCOMEPAGE_TEXT "Your native video studio.$\r$\n$\r$\nDownload complete videos or precisely selected clips with the FrameGrab optical glass interface.$\r$\n$\r$\nThis setup includes the media engine and all required runtime tools.$\r$\n$\r$\nClick Next to choose your installation location."
  !insertmacro MUI_PAGE_WELCOME
!macroend

# electron-builder 26.0.12's StdUtils.GetParameter truncates /D at a space.
# Read the complete final /D argument, as required by the NSIS command-line contract.
!macro customInit
  Push $R0
  Push $R1
  Push $R2
  Push $R3
  ${StdUtils.GetAllParameters} $R0 "0"
  StrLen $R2 $R0
  StrCpy $R1 0
  ${DoWhile} $R1 < $R2
    StrCpy $R3 $R0 3 $R1
    ${If} $R3 == "/D="
      ${If} $R1 > 0
        IntOp $R3 $R1 - 1
        StrCpy $R3 $R0 1 $R3
      ${Else}
        StrCpy $R3 " "
      ${EndIf}
      ${If} $R3 == " "
        IntOp $R1 $R1 + 3
        StrCpy $INSTDIR $R0 "" $R1
        ${Break}
      ${EndIf}
    ${EndIf}
    IntOp $R1 $R1 + 1
  ${Loop}
  Pop $R3
  Pop $R2
  Pop $R1
  Pop $R0
!macroend
