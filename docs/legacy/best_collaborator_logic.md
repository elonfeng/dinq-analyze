# 最佳合作者判断逻辑文档

本文档详细说明了系统如何确定学者的最佳合作者。

## 概述

在我们的系统中，最佳合作者的判断主要基于**合作论文数量**，而不是基于引用次数。系统会从合作次数最多的合作者中，找出第一个不是学者自己的合作者作为最佳合作者。

## 详细流程

{'name':'Yann LeCun','abbreviated_name':'Y LeCun','affiliation':'Chief AI Scientist at Facebook & JT Schwarz Professor at the Courant Institute, New York University','email':None,'research_fields':['AI','machine learning','computer vision','robotics','image compression'],'total_citations':407618,'citations_5y':256738,'h_index':156,'h_index_5y':120,'yearly_citations':{'2006':1092,'2007':1307,'2008':1368,'2009':1593,'2010':1839,'2011':2214,'2012':2627,'2013':3498,'2014':4847,'2015':7995,'2016':13731,'2017':21210,'2018':31394,'2019':39396,'2020':43959,'2021':48260,'2022':48672,'2023':49602,'2024':50414,'2025':15790},'papers':[{'title':'Deep learning','year':'2015','author_position':1,'authors':['Y LeCun','Y Bengio','G Hinton'],'venue':'nature 521 (7553), 436-444, 2015','citations':'95359'},{'title':'Gradient-based learning applied to document recognition','year':'1998','author_position':1,'authors':['Y LeCun','L Bottou','Y Bengio','P Haffner'],'venue':'Proceedings of the IEEE 86 (11), 2278-2324, 1998','citations':'75333'},{'title':'Backpropagation applied to handwritten zip code recognition','year':'1989','author_position':1,'authors':['Y LeCun','B Boser','JS Denker','D Henderson','RE Howard','W Hubbard','...'],'venue':'Neural computation 1 (4), 541-551, 1989','citations':'18726'},{'title':'Convolutional networks for images, speech, and time series','year':'1995','author_position':1,'authors':['Y LeCun','Y Bengio'],'venue':'The handbook of brain theory and neural networks 3361 (10), 1995, 1995','citations':'9189'},{'title':'The MNIST database of handwritten digits','year':'1998','author_position':1,'authors':['Y LeCun','C Cortes'],'venue':'','citations':'8555'},{'title':'OverFeat: Integrated Recognition, Localization and Detection using Convolutional Networks','year':'2014','author_position':6,'authors':['P Sermanet','D Eigen','X Zhang','M Mathieu','R Fergus','Y LeCun'],'venue':'International Conference on Learning Representations (ICLR 2014), 2014','citations':'8020'},{'title':'Character-level convolutional networks for text classification','year':'2015','author_position':3,'authors':['X Zhang','J Zhao','Y LeCun'],'venue':'Advances in neural information processing systems 28, 2015','citations':'7846'},{'title':'Efficient backprop','year':'2002','author_position':1,'authors':['Y LeCun','L Bottou','GB Orr','KR Müller'],'venue':'Neural networks: Tricks of the trade, 9-50, 2002','citations':'7737'},{'title':'Handwritten digit recognition with a back-propagation network','year':'1990','author_position':1,'authors':['Y LeCun','B Boser','JS Denker','D Henderson','RE Howard','W Hubbard','...'],'venue':'Advances in neural information processing systems 2, NIPS 1989, 396-404, 1990','citations':'7078'},{'title':'Dimensionality reduction by learning an invariant mapping','year':'2006','author_position':3,'authors':['R Hadsell','S Chopra','Y LeCun'],'venue':'Computer vision and pattern recognition 2006. CVPR 2006. IEEE computer\xa0…, 2006','citations':'6883'},{'title':'Spectral Networks and Locally Connected Networks on Graphs','year':'2014','author_position':4,'authors':['J Bruna','W Zaremba','A Szlam','Y LeCun'],'venue':'International Conference on Learning Representations (ICLR 2014), 2014','citations':'6821'},{'title':'Optimal Brain Damage','year':'1990','author_position':1,'authors':['Y LeCun','JS Denker','SA Solla'],'venue':'Advances in neural information processing systems 2, NIPS 1989 2, 598-605, 1990','citations':'6627'},{'title':'MNIST handwritten digit database','year':'2010','author_position':1,'authors':['Y LeCun','C Cortes','C Burges'],'venue':'','citations':'6285'},{'title':'Learning a similarity metric discriminatively, with application to face verification','year':'2005','author_position':3,'authors':['S Chopra','R Hadsell','Y LeCun'],'venue':'2005 IEEE computer society conference on computer vision and pattern\xa0…, 2005','citations':'5813'},{'title':'Signature verification using a" siamese" time delay neural network','year':'1993','author_position':3,'authors':['J Bromley','I Guyon','Y LeCun','E Säckinger','R Shah'],'venue':'Advances in neural information processing systems 6, 1993','citations':'5567'},{'title':'Geometric deep learning: going beyond euclidean data','year':'2017','author_position':3,'authors':['MM Bronstein','J Bruna','Y LeCun','A Szlam','P Vandergheynst'],'venue':'IEEE Signal Processing Magazine 34 (4), 18-42, 2017','citations':'4514'},{'title':'A Closer Look at Spatiotemporal Convolutions for Action Recognition','year':'2017','author_position':5,'authors':['D Tran','H Wang','L Torresani','J Ray','Y LeCun','M Paluri'],'venue':'computer vision and pattern recognition conference (CVPR 2018), 2017','citations':'4066'},{'title':'Learning Hierarchical Features for Scene Labeling','year':'2013','author_position':4,'authors':['C Farabet','C Couprie','L Najman','Y LeCun'],'venue':'IEEE Transactions on Pattern Analysis and Machine Intelligence 8 (35), 1915-1929, 2013','citations':'3614'},{'title':'Regularization of neural networks using dropconnect','year':'2013','author_position':4,'authors':['L Wan','M Zeiler','S Zhang','Y LeCun','R Fergus'],'venue':'30th International Conference on Machine Learning (ICML 2013), 1058-1066, 2013','citations':'3507'},{'title':'What is the best multi-stage architecture for object recognition?','year':'2009','author_position':4,'authors':['K Jarrett','K Kavukcuoglu','MA Ranzato','Y LeCun'],'venue':'Computer Vision, 2009. ICCV 2009. IEEE 12th International Conference on\xa0…, 2009','citations':'3242'},{'title':'Convolutional networks and applications in vision','year':'2010','author_position':1,'authors':['Y LeCun','K Kavukcuoglu','C Farabet'],'venue':'Proceedings of 2010 IEEE international symposium on circuits and systems\xa0…, 2010','citations':'3181'},{'title':'Barlow twins: Self-supervised learning via redundancy reduction','year':'2021','author_position':4,'authors':['J Zbontar','L Jing','I Misra','Y LeCun','S Deny'],'venue':'International Conference on Machine Learning (ICML) 139, 12310-12320, 2021','citations':'2882'},{'title':'Deep multi-scale video prediction beyond mean square error','year':'2015','author_position':3,'authors':['M Mathieu','C Couprie','Y LeCun'],'venue':'international Conference on Learning Representations (ICLR 2016), 2015','citations':'2412'},{'title':'Learning fast approximations of sparse coding','year':'2010','author_position':2,'authors':['K Gregor','Y Lecun'],'venue':'Machine Learning (ICML), 2010, International Conference on, 1-8, 2010','citations':'2273'},{'title':'Exploiting linear structure within convolutional networks for efficient evaluation','year':'2014','author_position':4,'authors':['EL Denton','W Zaremba','J Bruna','Y LeCun','R Fergus'],'venue':'Advances in neural information processing systems 27, 2014','citations':'2182'},{'title':'Deep convolutional networks on graph-structured data','year':'2015','author_position':3,'authors':['M Henaff','J Bruna','Y LeCun'],'venue':'arXiv preprint arXiv:1506.05163, 2015','citations':'2120'},{'title':'Joint training of a convolutional network and a graphical model for human pose estimation','year':'2014','author_position':3,'authors':['JJ Tompson','A Jain','Y LeCun','C Bregler'],'venue':'Advances in neural information processing systems, 1799-1807, 2014','citations':'2093'},{'title':'Learning methods for generic object recognition with invariance to pose and lighting','year':'2004','author_position':1,'authors':['Y LeCun','FJ Huang','L Bottou'],'venue':'Proceedings of the 2004 IEEE Computer Society Conference on Computer Vision\xa0…, 2004','citations':'1980'},{'title':'A tutorial on energy-based learning','year':'2006','author_position':1,'authors':['Y LeCun','S Chopra','R Hadsell','M Ranzato','F Huang'],'venue':'Predicting Structured Data, 2006','citations':'1969'},{'title':'Efficient object localization using convolutional networks','year':'2014','author_position':4,'authors':['J Tompson','R Goroshin','A Jain','Y LeCun','C Bregler'],'venue':'computer Vision and Pattern Recognition (CVPR 2015), 2014','citations':'1967'},{'title':'Scaling learning algorithms towards AI','year':'2007','author_position':2,'authors':['Y Bengio','Y LeCun'],'venue':'Large-scale kernel machines 34 (5), 1-41, 2007','citations':'1966'},{'title':'Efficient learning of sparse representations with an energy-based model','year':'2006','author_position':4,'authors':['MA Ranzato','C Poultney','S Chopra','Y LeCun'],'venue':'Advances in neural information processing systems 19, NIPS 2006 19, 1137-1144, 2006','citations':'1929'},{'title':'A theoretical analysis of feature pooling in visual recognition','year':'2010','author_position':3,'authors':['YL Boureau','J Ponce','Y LeCun'],'venue':'Machine Learning (ICML), 2010, International Conference on, 2010','citations':'1924'},{'title':'Comparison of Learning Algorithms for Handwritten Digit Recognition','year':'1995','author_position':1,'authors':['Y LeCun','L Jackel','L Bottou','A Brunot','C Cortes','J Denker','H Drucker','...'],'venue':'International Conference on Artificial Neural Networks, 53-60, 1995','citations':'1889'},{'title':'Generalization and network design strategies','year':'1989','author_position':1,'authors':['Y LeCun'],'venue':'Connectionism in perspective 19 (143-155), 18, 1989','citations':'1838'},{'title':'Very deep convolutional networks for natural language processing','year':'2016','author_position':4,'authors':['A Conneau','H Schwenk','L Barrault','Y Lecun'],'venue':'arXiv preprint arXiv:1606.01781 2 (1), 2016','citations':'1766'},{'title':'Object recognition with gradient-based learning','year':'1999','author_position':5,'authors':['DA Forsyth','JL Mundy','V di Gesú','R Cipolla','Y LeCun','P Haffner','L Bottou','...'],'venue':'Shape, contour and grouping in computer vision, 319-345, 1999','citations':'1741'},{'title':'The Loss Surface of Multilayer Networks','year':'2015','author_position':5,'authors':['A Choromanska','M Henaff','M Mathieu','G Ben Arous','Y LeCun'],'venue':'AI & Statistics (AIStats 2015), 2015','citations':'1728'},{'title':'Stereo Matching by Training a Convolutional Neural Network to Compare Image Patches','year':'2016','author_position':2,'authors':['J Žbontar','Y LeCun'],'venue':'Journal of Machine Learning Research 17, 1-32, 2016','citations':'1676'},{'title':'Energy-based generative adversarial network','year':'2016','author_position':3,'authors':['J Zhao','M Mathieu','Y LeCun'],'venue':'international Conference on Learning Representations (ICLR 2017), 2016','citations':'1675'},{'title':'Unsupervised learning of invariant feature hierarchies with applications to object recognition','year':'2007','author_position':4,'authors':['MA Ranzato','FJ Huang','YL Boureau','Y LeCun'],'venue':'Computer Vision and Pattern Recognition, 2007. CVPR 2007. IEEE Conference on\xa0…, 2007','citations':'1636'},{'title':'Deep learning made easier by linear transformations in perceptrons','year':'2012','author_position':3,'authors':['T Raiko','H Valpola','Y LeCun'],'venue':"International Conference on AI and Statistics (AISTAT'12), 2012",'citations':'1504'},{'title':'Learning mid-level features for recognition','year':'2010','author_position':3,'authors':['Y Boureau','F Bach','Y LeCun','J Ponce'],'venue':'Computer Vision and Pattern Recognition 2010. CVPR 2010. IEEE Conference on\xa0…, 2010','citations':'1472'},{'title':'VICReg: Variance-invariance-covariance regularization for self-supervised learning','year':'2022','author_position':3,'authors':['A Bardes','J Ponce','Y LeCun'],'venue':'International Conference on Learning Representations (ICLR 22), 2022','citations':'1302'},{'title':'Pushing stochastic gradient towards second-order methods–backpropagation learning with transformations in nonlinearities','year':'2013','author_position':4,'authors':['T Vatanen','T Raiko','H Valpola','Y LeCun'],'venue':'International conference on neural information processing, 442-449, 2013','citations':'1271'},{'title':'LeNet-5, convolutional neural networks','year':'2015','author_position':1,'authors':['Y LeCun'],'venue':'URL: http://yann. lecun. com/exdb/lenet 20 (5), 14, 2015','citations':'1233'},{'title':'A theoretical framework for back-propagation','year':'1988','author_position':1,'authors':['Y LeCun'],'venue':'Proceedings of the 1988 Connectionist Models Summer School, 21-28, 1988','citations':'1199'},{'title':'Sparse feature learning for deep belief networks','year':'2008','author_position':3,'authors':['MA Ranzato','Y Boureau','Y LeCun'],'venue':'Advances in neural information processing systems, 1185-1192, 2008','citations':'1196'},{'title':'Pedestrian detection with unsupervised multi-stage feature learning','year':'2013','author_position':4,'authors':['P Sermanet','K Kavukcuoglu','S Chintala','Y LeCun'],'venue':'IEEE Conference on Computer Vision and Pattern Recognition (CVPR 2013), 3626\xa0…, 2013','citations':'1132'},{'title':'MNIST handwritten digit database. 2010','year':'2010','author_position':1,'authors':['Y LeCun','C Cortes','C Burges'],'venue':'URL http://yann. lecun. com/exdb/mnist 7 (23), 6, 2010','citations':'1127'},{'title':'Comparison of classifier methods: a case study in handwritten digit recognition','year':'1994','author_position':7,'authors':['L Bottou','C Cortes','JS Denker','H Drucker','I Guyon','LD Jackel','Y LeCun','...'],'venue':'Proceedings of the 12th IAPR International Conference on Pattern Recognition\xa0…, 1994','citations':'1111'},{'title':'Traffic sign recognition with multi-scale convolutional networks','year':'2011','author_position':2,'authors':['P Sermanet','Y LeCun'],'venue':'The 2011 international joint conference on neural networks, 2809-2813, 2011','citations':'1082'},{'title':'Real-time continuous pose recovery of human hands using convolutional networks','year':'2014','author_position':3,'authors':['J Tompson','M Stein','Y Lecun','K Perlin'],'venue':'ACM Transactions on Graphics (ToG) 33 (5), 1-10, 2014','citations':'1014'},{'title':'Computing the stereo matching cost with a convolutional neural network','year':'2014','author_position':2,'authors':['J Žbontar','Y LeCun'],'venue':'Computer Vision and Pattern Recognition (CVPR 2015), 2014','citations':'1002'},{'title':'Mdetr-modulated detection for end-to-end multi-modal understanding','year':'2021','author_position':3,'authors':['A Kamath','M Singh','Y LeCun','G Synnaeve','I Misra','N Carion'],'venue':'Proceedings of the IEEE/CVF international conference on computer vision\xa0…, 2021','citations':'981'},{'title':'3rd International Conference on Learning Representations','year':'2015','author_position':4,'authors':['DP Kingma','J Ba','Y Bengio','Y LeCun'],'venue':'ICLR, San Diego, 2015','citations':'932'},{'title':'Convolutional learning of spatio-temporal features','year':'2010','author_position':3,'authors':['G Taylor','R Fergus','Y LeCun','C Bregler'],'venue':'Computer Vision ( ECCV), 2010, European Conference on, 140-153, 2010','citations':'923'},{'title':'Entropy-sgd: Biasing gradient descent into wide valleys','year':'2016','author_position':4,'authors':['P Chaudhari','A Choromanska','S Soatto','Y LeCun','C Baldassi','C Borgs','...'],'venue':'international Conference on Learning Representations (ICLR 2017), 2016','citations':'887'},{'title':'Fast Training of Convolutional Networks through FFTs','year':'2014','author_position':3,'authors':['M Mathieu','M Henaff','Y LeCun'],'venue':'International Conference on Learning Representations (ICLR 2014), 2014','citations':'860'},{'title':'Handwritten digit recognition: Applications of neural net chips and automatic learning','year':'1990','author_position':1,'authors':['Y LeCun','LD Hackel','B Boser','JS Denker','HP Graf','I Gyon','D Henderson','...'],'venue':'Neurocomputing 68, 303-318, 1990','citations':'839'},{'title':'Text understanding from scratch','year':'2015','author_position':2,'authors':['X Zhang','Y LeCun'],'venue':'arXiv preprint arXiv:1502.01710, 2015','citations':'817'},{'title':'Deep learning for AI','year':'2021','author_position':2,'authors':['Y Bengio','Y Lecun','G Hinton'],'venue':'Communications of the ACM 64 (7), 58-65, 2021','citations':'810'},{'title':'Convolutional neural networks applied to house numbers digit classification','year':'2012','author_position':3,'authors':['P Sermanet','S Chintala','Y LeCun'],'venue':'Proceedings of the 21st international conference on pattern recognition\xa0…, 2012','citations':'808'},{'title':'Off-road obstacle avoidance through end-to-end learning','year':'2006','author_position':1,'authors':['Y LeCun','U Muller','J Ben','E Cosatto','B Flepp'],'venue':'Advances in neural information processing systems 18, NIPS 2005 18, 739, 2006','citations':'781'},{'title':'Deep learning with elastic averaging SGD','year':'2015','author_position':3,'authors':['S Zhang','AE Choromanska','Y LeCun'],'venue':'Advances in neural information processing systems 28, 2015','citations':'777'},{'title':'Learning convolutional feature hierarchies for visual recognition','year':'2010','author_position':6,'authors':['K Kavukcuoglu','P Sermanet','YL Boureau','K Gregor','M Mathieu','Y LeCun'],'venue':'Advances in Neural Information Processing Systems 23, NIPS 2010 23, 2010','citations':'765'},{'title':'Efficient pattern recognition using a new transformation distance','year':'1992','author_position':2,'authors':['P Simard','Y LeCun','JS Denker'],'venue':'Advances in Neural Information Processing Systems 5, NIPS 1992, 50-58, 1992','citations':'752'},{'title':'Measuring the VC-dimension of a learning machine','year':'1994','author_position':-1,'authors':['V Vapnik','E Levin','Y Le Cun'],'venue':'Neural computation 6 (5), 851-876, 1994','citations':'705'},{'title':"Une procédure d'apprentissage pour réseau à seuil asymétrique (A learning scheme for asymmetric threshold networks)",'year':'1985','author_position':1,'authors':['Y LeCun'],'venue':'Proceedings of Cognitiva 85, 599-604, 1985','citations':'671'},{'title':'The role of over-parametrization in generalization of neural networks','year':'2019','author_position':4,'authors':['B Neyshabur','Z Li','S Bhojanapalli','Y LeCun','N Srebro'],'venue':'international conference on learning representations (ICLR 2019), 2019','citations':'668'},{'title':'Indoor Semantic Segmentation using depth information','year':'2013','author_position':4,'authors':['C Couprie','C Farabet','L Najman','Y LeCun'],'venue':'International Conference on Learning Representations (ICLR2013), 2013','citations':'631'},{'title':'Large Scale Online Learning.','year':'2003','author_position':2,'authors':['L Bottou','Y LeCun'],'venue':'Advances in Neural Information Processing Systems (NIPS 2003) 16, 2003','citations':'624'},{'title':'No more pesky learning rates','year':'2012','author_position':3,'authors':['T Schaul','S Zhang','Y LeCun'],'venue':"International Conference on Machine Learning 2013 (ICML'13) and arXiv:1206.1106, 2012",'citations':'605'},{'title':'Transformation invariance in pattern recognition—tangent distance and tangent propagation','year':'2002','author_position':2,'authors':['PY Simard','YA LeCun','JS Denker','B Victorri'],'venue':'Neural networks: tricks of the trade, 239-274, 2002','citations':'604'},{'title':'Disentangling factors of variation in deep representation using adversarial training','year':'2016','author_position':6,'authors':['MF Mathieu','JJ Zhao','J Zhao','A Ramesh','P Sprechmann','Y LeCun'],'venue':'Advances in neural information processing systems 29, 2016','citations':'574'},{'title':'NeuFlow: A Runtime Reconfigurable Dataflow Processor for Vision','year':'2011','author_position':6,'authors':['C Farabet','B Martini','B Corda','P Akselrod','E Culurciello','Y LeCun'],'venue':'Embedded Computer Vision Workshop at ICCV, 2011','citations':'547'},{'title':'Augmented language models: a survey','year':'2023','author_position':-1,'authors':['G Mialon','R Dessì','M Lomeli','C Nalmpantis','R Pasunuru','R Raileanu','...'],'venue':'arXiv preprint arXiv:2302.07842, 2023','citations':'542'},{'title':'Modèles connexionnistes de l’apprentissage','year':'1987','author_position':1,'authors':['Y LeCun'],'venue':'These de Doctorat, Universite Paris 6, 1987','citations':'538'},{'title':'Synergistic face detection and pose estimation with energy-based model','year':'2005','author_position':2,'authors':['M Osadchy','Y LeCun','ML Miller'],'venue':'In Advances in Neural Information Processing Systems 17 (NIPS 2004) 17, 2005','citations':'532'},{'title':'Classification of patterns of EEG synchronization for seizure prediction','year':'2009','author_position':3,'authors':['P Mirowski','D Madhavan','Y LeCun','R Kuzniecky'],'venue':'Clinical neurophysiology 120 (11), 1927-1940, 2009','citations':'525'},{'title':'Boosting and other ensemble methods','year':'1994','author_position':4,'authors':['H Drucker','C Cortes','LD Jackel','Y LeCun','V Vapnik'],'venue':'Neural computation 6 (6), 1289-1301, 1994','citations':'523'},{'title':'Cnp: An fpga-based processor for convolutional networks','year':'2009','author_position':4,'authors':['C Farabet','C Poulet','JY Han','Y LeCun'],'venue':'2009 International Conference on Field Programmable Logic and Applications\xa0…, 2009','citations':'515'},{'title':'Large-scale learning with svm and convolutional nets for generic object categorization','year':'2006','author_position':2,'authors':['FJ Huang','Y LeCun'],'venue':'Computer Vision and Pattern Recognition, 2006 IEEE Computer Society\xa0…, 2006','citations':'513'},{'title':'Neural networks: Tricks of the trade','year':'1998','author_position':1,'authors':['Y LeCun','L Bottou','GB Orr','KR Müller'],'venue':'Springer Lecture Notes in Computer Sciences 1524 (5-50), 6, 1998','citations':'493'},{'title':'Learning long‐range vision for autonomous off‐road driving','year':'2009','author_position':-1,'authors':['R Hadsell','P Sermanet','J Ben','A Erkan','M Scoffier','K Kavukcuoglu','...'],'venue':'Journal of Field Robotics 26 (2), 120-144, 2009','citations':'492'},{'title':'Original approach for the localisation of objects in images','year':'1994','author_position':3,'authors':['R Vaillant','C Monrocq','Y LeCun'],'venue':'Vision, Image and Signal Processing, IEE Proceedings- 141 (4), 245-250, 1994','citations':'483'},{'title':'Learning invariant features through topographic filter maps','year':'2009','author_position':4,'authors':['K Kavukcuoglu','MA Ranzato','R Fergus','Y LeCun'],'venue':'Computer Vision and Pattern Recognition 2009. CVPR 2009. IEEE Conference on\xa0…, 2009','citations':'461'},{'title':'Understanding dimensional collapse in contrastive self-supervised learning','year':'2021','author_position':3,'authors':['L Jing','P Vincent','Y LeCun','Y Tian'],'venue':'arXiv preprint arXiv:2110.09348, 2021','citations':'443'},{'title':'Learning process in an asymmetric threshold network','year':'1986','author_position':-1,'authors':['Y Le Cun'],'venue':'Disordered systems and biological organization, 233-240, 1986','citations':'441'},{'title':'Self-supervised learning from images with a joint-embedding predictive architecture','year':'2023','author_position':7,'authors':['M Assran','Q Duval','I Misra','P Bojanowski','P Vincent','M Rabbat','Y LeCun','...'],'venue':'Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern\xa0…, 2023','citations':'440'},{'title':'Super-Resolution with Deep Convolutional Sufficient Statistics','year':'2015','author_position':3,'authors':['J Bruna','P Sprechmann','Y LeCun'],'venue':'International Conference on Learning Representations (ICLR 2016), 2015','citations':'431'},{'title':'Toward automatic phenotyping of developing embryos from videos','year':'2005','author_position':3,'authors':['F Ning','D Delhomme','Y LeCun','F Piano','L Bottou','PE Barbano'],'venue':'IEEE Transactions on Image Processing 14 (9), 1360-1371, 2005','citations':'428'},{'title':'Fast Convolutional Nets With fbfft: A GPU Performance Evaluation','year':'2014','author_position':6,'authors':['N Vasilache','J Johnson','M Mathieu','S Chintala','S Piantino','Y LeCun'],'venue':'International Conference on Learning Representations (ICLR 2015), 2014','citations':'426'},{'title':'Transforming neural-net output levels to probability distributions','year':'1991','author_position':2,'authors':['J Denker','Y LeCun'],'venue':'Advances in Neural Information Processing Systems 3, NIPS 1990 3, 853-859, 1991','citations':'426'},{'title':'Deep learning, reinforcement learning, and world models','year':'2022','author_position':2,'authors':['Y Matsuo','Y LeCun','M Sahani','D Precup','D Silver','M Sugiyama','E Uchibe','...'],'venue':'Neural Networks 152, 267-275, 2022','citations':'421'},{'title':'A cookbook of self-supervised learning','year':'2023','author_position':-1,'authors':['R Balestriero','M Ibrahim','V Sobal','A Morcos','S Shekhar','T Goldstein','...'],'venue':'arXiv preprint arXiv:2304.12210, 2023','citations':'403'},{'title':'Hardware accelerated convolutional neural networks for synthetic vision systems','year':'2010','author_position':5,'authors':['C Farabet','B Martini','P Akselrod','S Talay','Y LeCun','E Culurciello'],'venue':'Proceedings of 2010 IEEE International Symposium on Circuits and Systems\xa0…, 2010','citations':'402'},{'title':'Ask the locals: multi-way local pooling for image recognition','year':'2011','author_position':5,'authors':['YL Boureau','N Le Roux','F Bach','J Ponce','Y LeCun'],'venue':"International Conference on Computer Vision (ICCV'11), 2011",'citations':'388'},{'title':'Adversarially Regularized Autoencoders for Generating Discrete Structures','year':'2018','author_position':5,'authors':['J Zhao','Y Kim','K Zhang','AM Rush','Y LeCun'],'venue':'International Conference on Machine Learning (ICML 2018), 2018','citations':'387'},{'title':'High quality document image compression with DjVu','year':'1998','author_position':-1,'authors':['L Bottou','P Haffner','PG Howard','P Simard','Y Bengio','Y Le Cun'],'venue':'Journal of Electronic Imaging 7 (3), 410-426, 1998','citations':'386'}],'years_of_papers':{2015:10,1998:4,1989:2,1995:2,2014:9,2002:2,1990:3,2006:5,2010:9,2005:3,1993:1,2017:2,2013:5,2009:5,2021:4,2004:1,2007:2,2016:5,1999:1,2012:3,2022:2,1988:1,2008:1,1994:4,2011:3,1992:1,1985:1,2019:1,2003:1,2023:3,1987:1,1986:1,1991:1,2018:1}}

### 1. 统计合作者出现次数

首先，系统会遍历学者的所有论文，统计每个合作者出现的次数：

```python
# Extract coauthors from publication data
coauthor_counter = Counter()
coauthor_papers = {}  # Dictionary to store papers by each coauthor
papers = author_data.get('papers', [])

# ...

for paper in papers:
    authors = paper.get('authors', [])
    # Remove the main author from the list (all forms) and filter out "..." placeholders
    filtered_authors = [a for a in authors if a not in exclude_names and a != "..." and not a.strip() == ""]

    for coauthor in filtered_authors:
        coauthor_counter[coauthor] += 1
```

这里使用 Python 的 `Counter` 对象来统计每个合作者在论文中出现的次数。同时，系统会过滤掉主要作者自己的名字（包括各种变体）和无效的作者名（如 "..."）。

### 2. 获取前10名合作者

然后，系统会获取合作次数最多的前10名合作者：

```python
for coauthor, count in coauthor_counter.most_common(10):
    # ...
    top_coauthors.append({
        'name': coauthor,
        'coauthored_papers': count,
        'best_paper': best_paper or {'title': 'Unknown', 'citations': 0}
    })
```

这里使用 `most_common(10)` 方法获取合作次数最多的前10名合作者。`most_common()` 方法会根据合作次数（即 `coauthor_counter` 中的计数值）对合作者进行降序排序，然后返回前N个元素。

### 3. 找出最佳合作者

接下来，系统会从这些合作者中找出第一个不是学者自己的合作者作为最佳合作者：

```python
most_frequent = None
if top_coauthors:
    # 确保最佳合作者不是作者自己
    for coauthor_info in top_coauthors:
        coauthor_name = coauthor_info['name']
        # 使用改进的方法检查是否是作者自己
        is_same = self.is_same_person(main_author_full, coauthor_name)
        logger.info(f"Checking if '{main_author_full}' and '{coauthor_name}' are the same person: {is_same}")

        if not is_same:
            most_frequent = coauthor_info
            logger.info(f"Most frequent collaborator: {most_frequent['name']} with {most_frequent['coauthored_papers']} papers")
            logger.info(f"Best paper with most frequent collaborator: '{most_frequent['best_paper'].get('title', '')}' in {most_frequent['best_paper'].get('venue', '')}")
            break
        else:
            logger.info(f"Skipping '{coauthor_name}' as it appears to be the same person as '{main_author_full}'")
```

这里会遍历前10名合作者，使用 `is_same_person` 方法检查合作者是否是学者自己。如果不是，就将其作为最佳合作者。

### 4. 查找最佳论文

对于每个合作者，系统还会找出与该合作者合作的引用次数最多的论文作为"最佳论文"：

```python
# Find the most cited paper with this coauthor
best_paper = None
max_citations = -1

for paper in coauthor_papers.get(coauthor, []):
    try:
        citations = int(paper.get('citations', 0))
        if citations > max_citations:
            max_citations = citations
            best_paper = paper
            logger.debug(f"Found better paper for {coauthor}: '{paper.get('title', '')}' with {citations} citations")
    except (ValueError, TypeError):
        logger.warning(f"Could not convert citations to integer for paper: {paper.get('title', '')}")
        continue
```

这里会遍历与该合作者合作的所有论文，找出引用次数最多的论文作为"最佳论文"。

### 5. 处理特殊情况

如果前10名合作者都被识别为学者自己，系统会尝试在更多的合作者中查找：

```python
# 如果所有合作者都被排除了（极少见的情况）
if not most_frequent and top_coauthors:
    logger.warning(f"All top coauthors appear to be variants of the main author's name. Searching for next best collaborator.")
    # 尝试找到第二批合作者
    for coauthor, count in coauthor_counter.most_common(20)[10:]:
        # 跳过已经在top_coauthors中的合作者
        if any(info['name'] == coauthor for info in top_coauthors):
            continue

        # 检查是否是作者自己
        if self.is_same_person(main_author_full, coauthor):
            continue

        # 找到最佳论文
        best_paper = None
        max_citations = -1
        for paper in coauthor_papers.get(coauthor, []):
            try:
                citations = int(paper.get('citations', 0))
                if citations > max_citations:
                    max_citations = citations
                    best_paper = paper
            except (ValueError, TypeError):
                continue

        if best_paper:
            most_frequent = {
                'name': coauthor,
                'coauthored_papers': count,
                'best_paper': best_paper
            }
            logger.info(f"Using alternative collaborator: {most_frequent['name']} with {most_frequent['coauthored_papers']} papers")
            break
```

这里会查找排名11-20的合作者，找出第一个不是学者自己的合作者作为最佳合作者。

### 6. 创建空结果

如果仍然没有找到合适的合作者，系统会创建一个空的结果：

```python
# 如果仍然没有找到合适的合作者，创建一个空的结果
if not most_frequent:
    logger.warning(f"Could not find any suitable collaborator. Creating empty result.")
    most_frequent = {
        'name': 'No suitable collaborator found',
        'coauthored_papers': 0,
        'best_paper': {'title': 'N/A', 'year': 'N/A', 'venue': 'N/A', 'citations': 0}
    }
```

## 名字匹配算法

系统使用 `is_same_person` 方法来检查合作者是否是学者自己。这个方法考虑了多种情况：

1. 完全相同的名字（不区分大小写）
2. 已知研究者的特殊变体（如 "Yann LeCun" 和 "Y LeCun"）
3. 姓氏相同，名字部分是缩写（如 "John Smith" 和 "J. Smith"）
4. 姓氏相同，名字部分完全匹配
5. 姓氏相同，一方只有姓氏，另一方有完整名字
6. 姓氏相同，名字部分是首字母缩写（如 "GE Hinton" 和 "Geoffrey E Hinton"）
7. 姓氏相同，第一个名字相同，其他名字是中间名
8. 名字中包含连字符或空格的变体（如 "Jean-Baptiste" 和 "Jean Baptiste"）
9. 名字中包含缩写的变体（如 "J.B. Smith" 和 "Jean-Baptiste Smith"）

## 示例

以 Yann LeCun 为例，系统会：

1. 统计每个合作者出现的次数，发现 L Bottou 与他合作了10篇论文
2. 获取合作次数最多的前10名合作者，包括 L Bottou
3. 检查 L Bottou 是否是 Yann LeCun 自己，结果是否定的
4. 将 L Bottou 选为最佳合作者
5. 找出与 L Bottou 合作的引用次数最多的论文："Gradient-based learning applied to document recognition"（75333次引用）

## 关于 most_common(10)

`most_common(10)` 是 Python 的 `Counter` 类的一个方法，它会返回计数器中出现次数最多的前10个元素。这些元素按照出现次数从高到低排序。

在我们的系统中，`coauthor_counter.most_common(10)` 会返回与学者合作次数最多的前10名合作者，按照合作论文数量从多到少排序。

例如，如果 `coauthor_counter` 包含以下数据：

```
{
    "L Bottou": 10,
    "Y Bengio": 8,
    "G Hinton": 7,
    "J Denker": 5,
    ...
}
```

那么 `coauthor_counter.most_common(10)` 会返回：

```
[("L Bottou", 10), ("Y Bengio", 8), ("G Hinton", 7), ("J Denker", 5), ...]
```

这确保了我们选择的最佳合作者是与学者合作次数最多的合作者（排除学者自己）。

## 注意事项

1. 最佳合作者的判断主要基于合作论文数量，而不是基于引用次数。
2. 系统会过滤掉学者自己的各种名字变体，确保最佳合作者不是学者自己。
3. 如果前10名合作者都被识别为学者自己，系统会尝试在更多的合作者中查找。
4. 如果仍然没有找到合适的合作者，系统会创建一个空的结果。
5. 最佳论文的判断基于引用次数，而不是基于合作次数。
