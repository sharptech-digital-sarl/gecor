import { Dialog, DialogTitle, DialogContent } from '@mui/material'
import { useTranslation } from 'react-i18next'
import PasswordChangeFlow from './PasswordChangeFlow'

type Props = {
  open: boolean
  onSuccess: () => void | Promise<void>
}

export default function ForcedPasswordChangeDialog({ open, onSuccess }: Props) {
  const { t } = useTranslation()

  return (
    <Dialog
      open={open}
      disableEscapeKeyDown
      fullWidth
      maxWidth="sm"
      slotProps={{
        backdrop: { onClick: (e) => e.stopPropagation() },
      }}
    >
      <DialogTitle>{t('settings.forcedPasswordChangeTitle')}</DialogTitle>
      <DialogContent sx={{ pb: 3 }}>
        <PasswordChangeFlow
          variant="dialog"
          intro={t('settings.forcedPasswordChangeIntro')}
          onSuccess={onSuccess}
        />
      </DialogContent>
    </Dialog>
  )
}
