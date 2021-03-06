import os
import random

import torch
import torchvision
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, json, render_template, request, send_from_directory
from flask_pymongo import PyMongo
from torchvision import transforms
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

app = Flask(__name__)
app.config['MONGO_URI'] = 'mongodb+srv://jla597:jla597@scanpay-5whgk.mongodb.net/scan_pay?ssl=true&ssl_cert_reqs' \
                          '=CERT_NONE'
mongo = PyMongo(app)

model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
in_features = model.roi_heads.box_predictor.cls_score.in_features
model.roi_heads.box_predictor = FastRCNNPredictor(in_features, 100)
# model.load_state_dict(torch.load(
#     os.path.join('static', 'models','model_gpu.pth' if torch.cuda.is_available() else 'model_cpu.pth')))
model.load_state_dict(torch.load(os.path.join('static', 'models', 'model_cpu.pth')))
model.eval()


def parse_target(target):
    temp = target[0]
    target = {'labels': temp['labels'].tolist(), 'boxes': temp['boxes'].tolist(), 'names': [], 'prices': []}
    data = mongo.db.food_price.find({'label': {'$in': temp['labels'].tolist()}})
    for item in data:
        target['names'].append(item['name'])
        target['prices'].append(item['price'])
    return target


def annotate_image(image, target):
    font = ImageFont.truetype(os.path.join('assets', 'fonts', 'font.ttf'), 24)
    draw = ImageDraw.Draw(image)
    boxes = target['boxes']
    names = target['names']
    prices = target['prices']
    for i in range(len(boxes)):
        p1, p2 = (boxes[i][0], boxes[i][1]), (boxes[i][2], boxes[i][3])
        p1 = int(p1[0]), int(p1[1])
        p2 = int(p2[0]), int(p2[1])
        color = (random.randint(127, 255), random.randint(127, 255), random.randint(127, 255))
        draw.rectangle((p1, p2), outline=color, width=4)
        text = names[i] + '  CDN$ ' + str(prices[i])
        draw.text((p1[0] + 8, p1[1] + 8), text, fill=color, font=font)
    return image


def clear_files(func):
    def wrapper():
        for image in os.listdir(os.path.join('static', 'images')):
            os.remove(os.path.join('static', 'images', image))
        res = func()
        return res
    wrapper.__name__ = func.__name__
    return wrapper


@app.route('/')
def index():
    if not os.path.exists(os.path.join('static', 'images')):
        os.makedirs(os.path.join('static', 'images'))
    return render_template('index.html')


@app.route('/', methods=['POST'])
@clear_files
def detect():
    image = request.files['image']
    if image and ('.' in image.filename and image.filename.rsplit('.', 1)[1] in {'jpeg', 'jpg'}):
        path = os.path.join('static', 'images', 'image') + str(random.randrange(1 << 16))
        image.save(path)
        image = Image.open(path).convert('RGB')
        target = model([transforms.ToTensor()(image)])
        target = parse_target(target)
        image = annotate_image(image, target)
        os.remove(path)
        path = path + '_annotated.jpg'
        image.save(path)
        return json.jsonify({
            'status': 'success',
            'data': {
                'image': path,
                'labels': target['labels'],
                'names': target['names'],
                'prices': target['prices'],
            }
        })
    return json.jsonify({
        'status': 'fail',
        'data': {
            'image': None,
            'labels': None,
            'names': None,
            'prices': None,
        }
    })


@app.route('/static/images/<path:filename>')
def get_file(filename):
    return send_from_directory(os.path.join('static', 'images'), filename)


@app.route('/favicon.ico')
def get_favicon():
    return send_from_directory(os.path.join('assets', 'icons'), 'favicon.ico')


if __name__ == '__main__':
    app.run()
