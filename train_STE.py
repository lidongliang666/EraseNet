import os
import math
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.backends.cudnn as cudnn
from PIL import Image
import numpy as np
from torch.autograd import Variable
from torchvision.utils import save_image
from torchvision import datasets
from torch.utils.data import DataLoader
from torchvision import utils
from data.dataloader import ErasingData,ErasingDataWithoutMask
from loss.Loss import LossWithGAN_STE, LossWithGAN_STE_WithoutMask
from models.Model import VGG16FeatureExtractor
from models.sa_gan import STRnet2

torch.set_num_threads(5)

os.environ["CUDA_VISIBLE_DEVICES"] = "3"    ### set the gpu as No....

parser = argparse.ArgumentParser()
parser.add_argument('--numOfWorkers', type=int, default=0,
                    help='workers for dataloader')
parser.add_argument('--modelsSavePath', type=str, default='',
                    help='path for saving models')
parser.add_argument('--logPath', type=str,
                    default='')
parser.add_argument('--batchSize', type=int, default=16)
parser.add_argument('--loadSize', type=int, default=512,
                    help='image loading size')
parser.add_argument('--dataRoot', type=str,
                    default='')
parser.add_argument('--pretrained',type=str, default='', help='pretrained models for finetuning')
parser.add_argument('--num_epochs', type=int, default=500, help='epochs')
parser.add_argument("--cuda",action='store_true')
parser.add_argument("--hasmask",action="store_true")
args = parser.parse_args()

print(args)
def visual(image):
    im = image.transpose(1,2).transpose(2,3).detach().cpu().numpy()
    Image.fromarray(im[0].astype(np.uint8)).show()


cuda = torch.cuda.is_available() and args.cuda
if cuda:
    print('Cuda is available!')
    cudnn.enable = True
    cudnn.benchmark = True

batchSize = args.batchSize
loadSize = (args.loadSize, args.loadSize)

if not os.path.exists(args.modelsSavePath):
    os.makedirs(args.modelsSavePath)

dataRoot = args.dataRoot

# import pdb;pdb.set_trace()
if args.hasmask:
    Erase_data = ErasingData(dataRoot, loadSize, training=True)
    criterion = LossWithGAN_STE(args.logPath, VGG16FeatureExtractor(), lr=0.00001, betasInit=(0.0, 0.9), Lamda=10.0)
    netG = STRnet2(3)
else:
    Erase_data = ErasingDataWithoutMask(dataRoot,loadSize,training=True)
    criterion = LossWithGAN_STE_WithoutMask(args.logPath, VGG16FeatureExtractor(), lr=0.00001, betasInit=(0.0, 0.9), Lamda=10.0,hasmask=False)
    netG = STRnet2(3,outmask=False)
Erase_data = DataLoader(Erase_data, batch_size=batchSize, 
                         shuffle=True, num_workers=args.numOfWorkers, drop_last=False, pin_memory=True)

if args.pretrained != '':
    print('loaded ')
    netG.load_state_dict(torch.load(args.pretrained))

numOfGPUs = torch.cuda.device_count()

if cuda:
    netG = netG.cuda()
    if numOfGPUs > 1:
        netG = nn.DataParallel(netG, device_ids=range(numOfGPUs))

count = 1


G_optimizer = optim.Adam(netG.parameters(), lr=0.0001, betas=(0.5, 0.9))




if cuda:
    criterion = criterion.cuda()

    if numOfGPUs > 1:
        criterion = nn.DataParallel(criterion, device_ids=range(numOfGPUs))

print('OK!')
num_epochs = args.num_epochs


torch.autograd.set_detect_anomaly(True)

for i in range(1, num_epochs + 1):
    netG.train()
    if args.hasmask:
        for k,(imgs, gt, masks, path) in enumerate(Erase_data):
            if cuda:
                imgs = imgs.cuda()
                gt = gt.cuda()
                masks = masks.cuda()
            netG.zero_grad()

            x_o1,x_o2,x_o3,fake_images,mm = netG(imgs)
            G_loss = criterion(imgs, masks, x_o1, x_o2, x_o3, fake_images, mm, gt, count, i)
            G_loss = G_loss.sum()
            G_optimizer.zero_grad()
            G_loss.backward()
            G_optimizer.step()  

            criterion.discriminator.zero_grad()
            D_real = criterion.discriminator(gt, None)
            D_real = D_real.mean().sum() * -1
            D_fake = criterion.discriminator(fake_images.detach(), None)
            D_fake = D_fake.mean().sum() * 1
            D_loss = torch.mean(F.relu(1.+D_real)) + \
                torch.mean(F.relu(1.+D_fake))  # SN-patch-GAN loss

            criterion.D_optimizer.zero_grad()
            D_loss.backward(retain_graph=True)
            criterion.D_optimizer.step()

            criterion.writer.add_scalar(
                'LossD/Discrinimator loss', D_loss.item(), count)     

            print('[{}/{}] Generator Loss of epoch{} is {}'.format(k,len(Erase_data),i, G_loss.item()))

            count += 1
    else:
        for k,(imgs, gt, path) in enumerate(Erase_data):
            if cuda:
                imgs = imgs.cuda()
                gt = gt.cuda()
            netG.zero_grad()
            r =  netG(imgs)
            x_o1,x_o2,x_o3,fake_images= r
            G_loss = criterion(imgs, x_o1, x_o2, x_o3, fake_images, gt, count, i)
            G_loss = G_loss.sum()
            G_optimizer.zero_grad()
            G_loss.backward()
            G_optimizer.step()   

            criterion.discriminator.zero_grad()
            D_real = criterion.discriminator(gt, None)
            D_real = D_real.mean().sum() * -1
            D_fake = criterion.discriminator(fake_images.detach(), None)
            D_fake = D_fake.mean().sum() * 1
            D_loss = torch.mean(F.relu(1.+D_real)) + \
                torch.mean(F.relu(1.+D_fake))  # SN-patch-GAN loss

            criterion.D_optimizer.zero_grad()
            D_loss.backward(retain_graph=True)
            criterion.D_optimizer.step()

            criterion.writer.add_scalar(
                'LossD/Discrinimator loss', D_loss.item(), count)       

            print('[{}/{}] Generator Loss of epoch{} is {},Discriminator Loss is {}'.format(k,len(Erase_data),i, G_loss.item(),D_loss.item()))

            count += 1


    
    if ( i % 10 == 0):
        if numOfGPUs > 1 :
            torch.save(netG.module.state_dict(), args.modelsSavePath +
                    '/STE_{}.pth'.format(i))
        else:
            torch.save(netG.state_dict(), args.modelsSavePath +
                    '/STE_{}.pth'.format(i))