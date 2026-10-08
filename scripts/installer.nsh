!macro customWelcomePage
  !insertmacro skipPageIfUpdated
  !define MUI_WELCOMEPAGE_TITLE "Welcome to FrameGrab ${VERSION}"
  !define MUI_WELCOMEPAGE_TEXT "Your native video studio.$\r$\n$\r$\nDownload complete videos or precisely selected clips with the FrameGrab optical glass interface.$\r$\n$\r$\nThis setup includes the media engine and all required runtime tools.$\r$\n$\r$\nClick Next to choose your installation location."
  !insertmacro MUI_PAGE_WELCOME
!macroend
