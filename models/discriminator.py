import torch
import torch.nn as nn
from .networks import ConvWithActivation, get_pad

##discriminator
class Discriminator_STE(nn.Module):
    def __init__(self, inputChannels, hasmask=True):
        super(Discriminator_STE, self).__init__()
        self.hasmask = hasmask
        cnum =32
        self.globalDis = nn.Sequential(
            ConvWithActivation(3, 2*cnum, 4, 2, padding=get_pad(256, 5, 2)),
            ConvWithActivation(2*cnum, 4*cnum, 4, 2, padding=get_pad(128, 5, 2)),
            ConvWithActivation(4*cnum, 8*cnum, 4, 2, padding=get_pad(64, 5, 2)),
            ConvWithActivation(8*cnum, 8*cnum, 4, 2, padding=get_pad(32, 5, 2)),
            ConvWithActivation(8*cnum, 8*cnum, 4, 2, padding=get_pad(16, 5, 2)),
            ConvWithActivation(8*cnum, 8*cnum, 4, 2, padding=get_pad(8, 5, 2)),            
        )
        if hasmask:
            self.localDis = nn.Sequential(
                ConvWithActivation(3, 2*cnum, 4, 2, padding=get_pad(256, 5, 2)),
                ConvWithActivation(2*cnum, 4*cnum, 4, 2, padding=get_pad(128, 5, 2)),
                ConvWithActivation(4*cnum, 8*cnum, 4, 2, padding=get_pad(64, 5, 2)),
                ConvWithActivation(8*cnum, 8*cnum, 4, 2, padding=get_pad(32, 5, 2)),
                ConvWithActivation(8*cnum, 8*cnum, 4, 2, padding=get_pad(16, 5, 2)),
                ConvWithActivation(8*cnum, 8*cnum, 4, 2, padding=get_pad(8, 5, 2)),
            )
        
        self.fusion = nn.Sequential(
            nn.Conv2d(512 if hasmask else 256, 1, kernel_size=4),
            nn.Sigmoid()
        )

    def forward(self, input, masks):
        global_feat = self.globalDis(input)

        if self.hasmask:
            local_feat = self.localDis(input * (1 - masks))

            concat_feat = torch.cat((global_feat, local_feat), 1)
            return self.fusion(concat_feat).view(input.size()[0],-1)
        else:
            return self.fusion(global_feat).view(input.size()[0],-1)

        # r = self.fusion(concat_feat)
        # print(r.shape)
        # r = r.view(input.size()[0], -1)
        # print(r.shape)
        # return self.fusion(concat_feat)
